import asyncio
import time
from datetime import datetime
from openai import AsyncOpenAI

from src.common.db_client import get_db_conn
from src.common.es_client import get_es_client
from src.common.logger import setup_logger
from src.resources.queries import SummarySQL
from src.resources.prompts import SummaryPrompts

# 로거 설정
logger = setup_logger('Summarizer', 'summary_async.log')

async def _generate_summary_async(client, model, text):
    """비동기 LLM 요약 요청"""
    try:
        if not text:
            return None
            
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SummaryPrompts.SYSTEM},
                {"role": "user", "content": f"Article Content:\n{text[:1500]}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"  [LLM API Error] {e}")
        return None

async def _process_article(idx, total, row, client, model_name, sem, es, index_name, conn):
    """개별 기사 처리 로직"""
    async with sem:
        db_id = row['id']
        es_id = row['es_id']
        
        try:
            # 1. ES 원문 조회
            try:
                res = await es.get(index=index_name, id=es_id)
                content = res['_source'].get('content', '')
            except Exception:
                logger.warning(f"[{idx}/{total}] ES 문서 없음 - ID: {db_id} (ES_ID: {es_id})")
                return

            if not content:
                logger.warning(f"[{idx}/{total}] 본문 내용 없음 - ID: {db_id}")
                return

            # 2. 요약 생성
            summary = await _generate_summary_async(client, model_name, content)

            # 3. 결과 업데이트 (개별 커밋)
            cur = conn.cursor()
            if summary:
                # [ES 저장] 요약 내용은 ES에만 저장
                await es.update(index=index_name, id=es_id, body={
                    "doc": {
                        "summary": summary, 
                        "summarized_at": datetime.now().isoformat()
                    }
                })
                
                # [DB 저장] 상태만 업데이트 (인자: 시간, ID)
                cur.execute(SummarySQL.UPDATE_COMPLETED, (db_id,))
                logger.info(f"[{idx}/{total}] ✅ 완료 - DB ID: {db_id}")
            else:
                cur.execute(SummarySQL.UPDATE_ERROR, (db_id,))
                logger.error(f"[{idx}/{total}] ❌ 실패 (LLM 응답 없음) - DB ID: {db_id}")
            
            conn.commit()
            cur.close()
            
        except Exception as e:
            logger.error(f"[{idx}/{total}] 처리 중 에러 (DB ID: {db_id}): {e}")
            if conn and conn.open:
                conn.rollback()

async def run(config, target_id=None):
    """Summarizer 메인 진입점"""
    logger.info("=== [Summarizer] 배치 작업 시작 ===")
    
    # 1. 자원 초기화
    es = get_es_client(config)
    conn = get_db_conn(config)
    
    # [Config Mapping] config.ini 섹션 참조
    # 1) LLM 설정
    if 'llm_async' in config:
        llm_conf = config['llm_async']
    else:
        llm_conf = config['llm_model']

    # 2) Summarizer 설정
    settings = config['summarizer_settings']
    
    async_client = AsyncOpenAI(
        api_key=llm_conf.get('api_key', 'dummy'), 
        base_url=llm_conf.get('base_url')
    )
    
    # 설정 변수 할당
    fetch_size = int(settings.get('fetch_size', 1000))
    concurrency = int(settings.get('concurrency', 8))
    model_name = llm_conf.get('model', 'gpt-3.5-turbo')
    index_name = config['elasticsearch'].get('source_index', 'dataset_articles')
    
    try:
        cur = conn.cursor()
        
        # 2. 대상 조회 (Target ID 분기)
        if target_id:
            logger.info(f"👉 [Target Mode] ID {target_id} 만 처리합니다.")
            cur.execute(SummarySQL.SELECT_TARGET_SINGLE, (target_id,))
        else:
            logger.info(f"👉 [Batch Mode] Summary 작업 대상 {fetch_size}건을 조회합니다.")
            # [핵심 수정] SummarySQL 사용 (LabelerSQL 아님)
            cur.execute(SummarySQL.SELECT_TARGET_BATCH, (fetch_size,))
            
        targets = cur.fetchall()
        cur.close()
        
        total = len(targets)
        if total == 0:
            logger.info("처리할 데이터가 없습니다.")
            return

        logger.info(f"총 {total}건의 작업을 시작합니다.")
        
        # 3. 비동기 태스크 생성 및 실행
        semaphore = asyncio.Semaphore(concurrency)
        tasks = [
            _process_article(i, total, row, async_client, model_name, semaphore, es, index_name, conn)
            for i, row in enumerate(targets, start=1)
        ]

        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        logger.info(f"=== [Summarizer] 작업 종료 (소요시간: {end_time - start_time:.2f}초) ===")

    except Exception as e:
        logger.error(f"치명적 오류 발생: {e}")
    finally:
        if conn and conn.open: conn.close()
        await es.close()
        await async_client.close()
