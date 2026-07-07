# Elasticsearch의 문서 ID와 dataset_id를 MySQL 데이터베이스의 es_id_inventory 테이블에 저장하는 스크립트
# content값 비교 용도로 사용

from elasticsearch import Elasticsearch, helpers
from utils.db_client import get_db_conn

def sync_es_ids_to_db():
    # 1. 연결 설정
    es = Elasticsearch(["http://localhost:9200"])
    conn = get_db_conn()
    cur = conn.cursor()
    
    index_name = "dataset_articles"
    batch_size = 5000  # 한 번에 DB에 넣을 단위
    data_buffer = []   # (es_id, dataset_id) 튜플을 저장할 버퍼
    total_count = 0

    print(f"[{index_name}] 인덱스에서 ID 및 dataset_id 추출 시작...")

    try:
        # 2. helpers.scan을 사용하여 모든 문서 스캔
        # _source=["dataset_id"] 로 설정하여 필요한 필드만 가져옴 (네트워크/메모리 최적화)
        scanner = helpers.scan(
            client=es,
            index=index_name,
            query={"query": {"match_all": {}}},
            _source=["dataset_id"],  # 가져올 필드 명시 (False 대신 리스트 사용)
            size=batch_size,
            scroll='5m'
        )

        for hit in scanner:
            es_id = hit["_id"]
            # dataset_id가 없을 경우 None 처리 (또는 기본값)
            dataset_id = hit.get("_source", {}).get("dataset_id")
            
            data_buffer.append((es_id, dataset_id))
            
            # 버퍼가 차면 DB에 Bulk Insert
            if len(data_buffer) >= batch_size:
                # INSERT 쿼리에 dataset_id 컬럼 추가
                cur.executemany("""
                    INSERT IGNORE INTO es_id_inventory (es_id, dataset_id) 
                    VALUES (%s, %s)
                """, data_buffer)
                conn.commit()
                
                total_count += len(data_buffer)
                print(f"현재까지 {total_count}개 삽입 완료...")
                data_buffer = []

        # 남은 데이터 처리
        if data_buffer:
            cur.executemany("""
                INSERT IGNORE INTO es_id_inventory (es_id, dataset_id) 
                VALUES (%s, %s)
            """, data_buffer)
            conn.commit()
            total_count += len(data_buffer)

        print(f"✅ 최종 완료! 총 {total_count}개의 ID가 저장되었습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    sync_es_ids_to_db()
