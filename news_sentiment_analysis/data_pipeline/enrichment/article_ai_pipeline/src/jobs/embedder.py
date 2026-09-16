import asyncio
from tqdm import tqdm
from openai import AsyncOpenAI
from elasticsearch import helpers

from src.common.db_client import get_db_conn
from src.common.es_client import get_es_client
from src.common.logger import setup_logger
from src.resources.queries import EmbedderSQL

logger = setup_logger('Embedder', 'embedder.log')

async def get_embedding(client, model_name, row_id, title, summary, target, themes):
    # [수정] 메타데이터 결합 로직 강화
    safe_title = title if title else ""
    safe_summary = summary if summary else ""
    safe_target = target if target else "General"
    safe_themes = themes if themes else "General"

    # LLM이 문맥을 더 잘 이해하도록 명시적 태그(Label)를 붙여줍니다.
    text_to_embed = (
        f"Target: {safe_target}\n"
        f"Theme: {safe_themes}\n"
        f"Title: {safe_title}\n"
        f"Summary: {safe_summary}"
    ).strip()
    
    if len(text_to_embed) < 10:
        return row_id, None, "Text too short (<10 chars)"

    try:
        response = await client.embeddings.create(
            input=text_to_embed,
            model=model_name
        )
        return row_id, response.data[0].embedding, None
        
    except Exception as e:
        return row_id, None, str(e)

def save_batch_db_flag(conn, data):
    """DB 상태 업데이트"""
    if not data: return
    ids = [(r_id,) for vec, r_id in data]
    with conn.cursor() as cur:
        cur.executemany(EmbedderSQL.UPDATE_STATUS, ids)

async def save_batch_es(es, data, es_id_map, index_name, model_name):
    """ES 벡터 업데이트"""
    if not data: return
    actions = []
    for vector, r_id in data:
        es_id = es_id_map.get(r_id)
        if not es_id: continue
        actions.append({
            "_op_type": "update",
            "_index": index_name,
            "_id": es_id,
            "doc": {
                "context_vector": vector,
                "embedding_model": model_name
            }
        })
    if actions:
        await helpers.async_bulk(es, actions, raise_on_error=False)

async def run(config, target_id=None):
    """Embedder 메인 진입점"""
    logger.info("=== [Embedder] 배치 작업 시작 ===")
    
    conn = get_db_conn(config)
    es = get_es_client(config)
    
    emb_conf = config['embedding_model']
    settings = config['embedder_settings']
    
    base_url = emb_conf.get('base_url', 'http://localhost:11434/v1')
    if not base_url.endswith("/v1"): 
        base_url = f"{base_url.rstrip('/')}/v1"
        
    client = AsyncOpenAI(base_url=base_url, api_key=emb_conf.get('api_key', 'ollama'))
    model_name = emb_conf.get('model', 'qllama/bge-m3:q4_k_m')
    
    fetch_size = int(settings.get('fetch_size', 1000))
    concurrency = int(settings.get('concurrency', 5))
    commit_interval = int(settings.get('commit_interval', 100))
    index_name = config['elasticsearch'].get('source_index', 'dataset_articles')

    try:
        cur = conn.cursor()
        
        if target_id:
            logger.info(f"👉 [Target Mode] ID {target_id}")
            cur.execute(EmbedderSQL.SELECT_TARGET_SINGLE, (target_id,))
        else:
            logger.info(f"👉 [Batch Mode] 임베딩 미완료 데이터 조회")
            cur.execute(EmbedderSQL.SELECT_TARGET_BATCH, (fetch_size,))
        
        rows = cur.fetchall()
        cur.close()

        if not rows:
            logger.info("처리할 데이터가 없습니다.")
            return
            
        logger.info(f"총 {len(rows)}건 처리 시작")
        
        # [수정] worker 호출 시 target, themes 전달
        sem = asyncio.Semaphore(concurrency)
        async def worker(r_id, r_title, r_summary, r_target, r_themes):
            async with sem:
                return await get_embedding(client, model_name, r_id, r_title, r_summary, r_target, r_themes)

        # 청크 단위 처리
        chunks = [rows[i:i+commit_interval] for i in range(0, len(rows), commit_interval)]
        pbar = tqdm(total=len(rows), desc="🧬 벡터 생성 중", ncols=100)
        
        for idx, chunk in enumerate(chunks):
            es_id_map = {r['id']: r['es_id'] for r in chunk}
            es_ids = list(es_id_map.values())
            
            # 1. ES 조회
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

            # 2. 임베딩 태스크 생성 (콜백 적용)
            tasks = []
            for row in chunk:
                summary = summary_map.get(row['es_id'], "")
                # [수정] row에서 target, themes 추출해서 전달
                task = asyncio.create_task(
                    worker(
                        row['id'], 
                        row['title'], 
                        summary, 
                        row.get('target'), 
                        row.get('themes')
                    )
                )
                task.add_done_callback(lambda _: pbar.update(1)) # 실시간 진행률
                tasks.append(task)
            
            # 대기
            results = await asyncio.gather(*tasks)
            
            # 3. 결과 수집
            valid_data = []
            for r_id, vec, error_msg in results:
                if error_msg:
                    tqdm.write(f"⚠️ [ID:{r_id}] 실패: {error_msg}")
                    continue
                if vec:
                    valid_data.append((vec, r_id))

            # 4. 저장
            if valid_data:
                try:
                    await save_batch_es(es, valid_data, es_id_map, index_name, model_name)
                    save_batch_db_flag(conn, valid_data)
                    conn.commit()
                    # 저장 로그 간소화
                except Exception as e:
                    conn.rollback()
                    logger.error(f"저장 중 에러: {e}")

        pbar.close()

    except Exception as e:
        logger.error(f"치명적 오류: {e}")
        conn.rollback()
    finally:
        if conn and conn.open: conn.close()
        await es.close()
        await client.close()
