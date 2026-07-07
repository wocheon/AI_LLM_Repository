import asyncio
import math
import re
from tqdm import tqdm
from openai import AsyncOpenAI
from elasticsearch import helpers

from src.common.db_client import get_db_conn
from src.common.es_client import get_es_client
from src.common.logger import setup_logger
from src.resources.queries import LabelerSQL
from src.resources.prompts import LabelerPrompts

logger = setup_logger('Labeler', 'labeler.log')

async def extract_all_info(client, model, row_id, title, summary):
    """LLM을 이용한 타겟, 테마, 감성 추출"""
    
    # 요약 정보가 없을 경우 대비
    safe_summary = summary if summary else "요약 정보 없음 (제목 기반 분석 필요)"
    user_prompt = LabelerPrompts.USER_TEMPLATE.format(title=title, summary=safe_summary)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": LabelerPrompts.SYSTEM},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=60,
            logprobs=True,
            top_logprobs=1
        )

        content = response.choices[0].message.content.strip()
        
        # Confidence Score 계산
        confidence_score = 0.0
        if response.choices[0].logprobs and response.choices[0].logprobs.content:
            logprobs = response.choices[0].logprobs.content
            token_probs = [math.exp(lp.logprob) for lp in logprobs]
            if token_probs:
                confidence_score = sum(token_probs) / len(token_probs)

        # 파싱 로직
        target, themes, score = None, None, None

        match_std = re.search(r"([^|]+)\|([^|]+)\|.*?(\d)", content)
        if match_std:
            target = match_std.group(1).strip()
            themes = match_std.group(2).strip()
            score = int(match_std.group(3))
        elif "|" in content:
            parts = content.split("|")
            if len(parts) == 2:
                target = parts[0].strip()
                rest = parts[1].strip()
                num_match = re.search(r'(\d+)$', rest)
                if num_match:
                    score = int(num_match.group(1))
                    themes = re.sub(r'\d+', '', rest).replace('는', '').replace('은', '').strip() or "일반"
        else:
            match_fallback = re.search(r'^([^\s]+).+?(\d)', content)
            if match_fallback:
                target = match_fallback.group(1).strip()
                score = int(match_fallback.group(2))
                themes = "기타"
                if target.endswith("는") or target.endswith("은"):
                    target = target[:-1]

        if target is None or score is None:
            return row_id, None, None, None, 0.0, f"Parsing Failed: {content}"

        if not themes: themes = "일반"

        # 정제
        target = re.sub(r"[\[\]\(\)\"\'…\.\.\.]", "", target).strip()
        bad_prefixes = ['target', 'entity', '타겟', 'subject']
        junk_targets = ['국가', '코로나19', '뉴스', '속보', '종합', '단독', '기획']

        if target.lower() in bad_prefixes or target.lower().startswith("target"):
            return row_id, None, None, None, 0.0, "Invalid Target Name"

        if len(target) > 10 or target in junk_targets: 
            target = "시장"; score = 0

        return row_id, target, themes, score, confidence_score, None

    except Exception as e:
        return row_id, None, None, None, 0.0, str(e)

def save_batch_db(conn, data):
    """DB 배치 업데이트"""
    if not data: return
    with conn.cursor() as cur:
        cur.executemany(LabelerSQL.UPDATE_RESULT, data)

async def save_batch_es(es, data, es_id_map, index_name):
    """ES 배치 업데이트"""
    if not data: return
    actions = []
    for tgt, thm, score, conf, r_id in data:
        es_id = es_id_map.get(r_id)
        if not es_id: continue
        actions.append({
            "_op_type": "update",
            "_index": index_name,
            "_id": es_id,
            "doc": {
                "sentiment_label": score,
                "confidence": conf,
                "target": tgt,   
                "themes": thm
            }
        })
    if actions:
        await helpers.async_bulk(es, actions, raise_on_error=False)

async def run(config, target_id=None):
    """Labeler 메인 진입점"""
    logger.info("=== [Labeler] 배치 작업 시작 ===")
    
    conn = get_db_conn(config)
    es = get_es_client(config)
    
    # 설정 로드
    if 'llm_async' in config:
        llm_conf = config['llm_async']
    else:
        llm_conf = config['llm_model']
        
    settings = config['labeler_settings']
    
    client = AsyncOpenAI(
        api_key=llm_conf.get('api_key', 'dummy'), 
        base_url=llm_conf.get('base_url')
    )
    model_name = llm_conf.get('model')

    fetch_size = int(settings.get('fetch_size', 1000))
    concurrency = int(settings.get('concurrency', 8))
    commit_interval = int(settings.get('commit_interval', 100))
    index_name = config['elasticsearch'].get('source_index', 'dataset_articles')

    try:
        cur = conn.cursor()
        
        if target_id:
            logger.info(f"👉 [Target Mode] ID {target_id}")
            cur.execute(LabelerSQL.SELECT_TARGET_SINGLE, (target_id,))
        else:
            logger.info(f"👉 [Batch Mode] 라벨링 미완료 데이터 조회 (Limit: {fetch_size})")
            cur.execute(LabelerSQL.SELECT_TARGET_BATCH, (fetch_size,))
            
        rows = cur.fetchall()
        cur.close()

        if not rows:
            logger.info("처리할 데이터가 없습니다.")
            return

        logger.info(f"총 {len(rows)}건 처리 시작")

        sem = asyncio.Semaphore(concurrency)
        async def worker(r_id, r_title, r_summary):
            async with sem:
                return await extract_all_info(client, model_name, r_id, r_title, r_summary)

        # 청크 단위 처리
        chunks = [rows[i:i + commit_interval] for i in range(0, len(rows), commit_interval)]
        
        # [수정] 실시간 진행률 표시를 위한 pbar 설정
        pbar = tqdm(total=len(rows), desc="🚀 라벨링 분석 중", ncols=100)

        for idx, chunk in enumerate(chunks):
            es_id_map = {r['id']: r['es_id'] for r in chunk if r.get('es_id')}
            es_ids = list(es_id_map.values())

            # 1. ES에서 Summary 조회
            summary_map = {}
            if es_ids:
                try:
                    es_res = await es.mget(index=index_name, ids=es_ids, _source=["summary"])
                    for doc in es_res['docs']:
                        if doc.get('found'):
                            summary_map[doc['_id']] = doc['_source'].get('summary', '')
                        else:
                            summary_map[doc['_id']] = ""
                except Exception as e:
                    logger.error(f"ES 조회 실패: {e}")
                    summary_map = {eid: "" for eid in es_ids}

            # 2. LLM 태스크 생성 및 콜백 등록
            tasks = []
            for row in chunk:
                summary_text = summary_map.get(row['es_id'], "")
                
                # create_task로 감싸서 콜백 등록
                task = asyncio.create_task(worker(row['id'], row['title'], summary_text))
                task.add_done_callback(lambda _: pbar.update(1)) # 완료 시 게이지 증가
                tasks.append(task)
            
            # 모든 작업 완료 대기
            results = await asyncio.gather(*tasks)

            # 3. 데이터 정제
            valid_data = []
            for r_id, tgt, thm, score, conf, error_msg in results:
                if error_msg:
                    tqdm.write(f"⚠️ [ID:{r_id}] 실패: {error_msg}")
                    continue
                
                if tgt is not None and score is not None:
                    valid_data.append((tgt, thm, score, conf, r_id))
            
            # 4. 저장 (남은 개수 상관없이 저장)
            if valid_data:
                try:
                    save_batch_db(conn, valid_data)
                    conn.commit()
                    await save_batch_es(es, valid_data, es_id_map, index_name)
                    # 저장 로그 간소화
                    # tqdm.write(f"[Chunk {idx+1}] 저장 완료 ({len(valid_data)}건)")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"저장 중 에러: {e}")
            else:
                tqdm.write(f"[Chunk {idx+1}] ⚠️ 유효 결과 없음")

        pbar.close()

    except Exception as e:
        logger.error(f"치명적 오류: {e}")
        conn.rollback()
    finally:
        if conn and conn.open: conn.close()
        await es.close()
        await client.close()
