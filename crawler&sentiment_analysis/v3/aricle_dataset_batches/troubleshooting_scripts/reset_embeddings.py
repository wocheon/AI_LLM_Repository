import asyncio
from src.common.config import load_config
from src.common.db_client import get_db_conn
from src.common.es_client import get_es_client
from src.common.logger import setup_logger

logger = setup_logger("ResetTool")

async def main():
    config = load_config('config.ini')
    conn = get_db_conn(config)
    es = get_es_client(config)
    index_name = config['elasticsearch']['source_index']

    try:
        # 1. MySQL 상태 초기화
        logger.info("1. MySQL 상태 초기화 중...")
        with conn.cursor() as cur:
            # summary가 완료된 건들에 한해 embedding만 다시 하도록 PENDING 처리
            sql = "UPDATE article_dataset SET embedding_status = 'PENDING' WHERE summary_status = 'COMPLETED'"
            cur.execute(sql)
            conn.commit()
            logger.info(f"   - {cur.rowcount}건 상태 변경 완료 (COMPLETED -> PENDING)")

        # 2. Elasticsearch 벡터 필드 삭제
        logger.info("2. Elasticsearch 벡터 데이터 삭제 중...")
        
        # update_by_query를 사용하여 특정 필드만 null로 초기화
        script = {
            "source": """
                ctx._source.context_vector = null;
                ctx._source.embedding_model = null;
            """,
            "lang": "painless"
        }
        
        # 모든 문서 대상 (혹은 query로 조건 필터링 가능)
        await es.update_by_query(
            index=index_name,
            body={
                "script": script,
                "query": {"match_all": {}}
            },
            wait_for_completion=True,
            request_timeout=300
        )
        logger.info("   - ES 벡터 필드 초기화 완료")

    except Exception as e:
        logger.error(f"작업 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()
        await es.close()

if __name__ == "__main__":
    asyncio.run(main())
