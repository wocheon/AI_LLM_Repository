# DB와 Elasticsearch 간의 문서 존재 여부 비교 스크립트
# DB 내 content 필드가 NULL이 아니고 'ERROR'가 아니며 'worker%'로 시작하지 않는 문서들을 대상으로
# Elasticsearch에 해당 문서가 존재하는지 확인
from datetime import datetime
import os
from utils.db_client import get_db_conn
from elasticsearch import Elasticsearch

def find_missing_docs():
    # 1. DB에서 ES ID 목록 가져오기
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, content 
            FROM article_dataset 
            WHERE content IS NOT NULL 
              AND content != 'ERROR'
              AND content NOT LIKE 'worker%'
        """)
        db_records = cur.fetchall()
        logger_info(f"총 DB 레코드 수: {len(db_records)}")
    except Exception as e:
        print(f"DB 연결 오류: {e}")
        return

    es = Elasticsearch(["http://localhost:9200"])
    missing_ids = []

    batch_size = 500
    total = len(db_records)

    for i in range(0, total, batch_size):
        batch = db_records[i:i+batch_size]
        es_ids = [row[1] for row in batch]

        # 2. ES 존재 여부 확인 (mget)
        try:
            res = es.mget(index="dataset_articles", ids=es_ids)
            existing_flags = [doc.get("found", False) for doc in res["docs"]]

            for (db_id, es_id), found in zip(batch, existing_flags):
                if not found:
                    missing_ids.append((db_id, es_id))
            
            print(f"진행 중: {i + len(batch)}/{total} (누락 발견: {len(missing_ids)})")
        except Exception as e:
            print(f"ES 조회 중 오류 발생: {e}")
            continue

    # 3. 별도 파일로 결과 저장
    if missing_ids:
        save_results(missing_ids)
    else:
        print("누락된 문서가 없습니다. 모든 데이터가 동기화되어 있습니다.")

    cur.close()
    conn.close()

def save_results(missing_ids):
    """결과를 파일로 저장하는 유틸리티"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 텍스트 파일 저장 (단순 확인용)
    txt_filename = f"missing_ids_{timestamp}.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write("DB_ID, ES_ID\n")
        for db_id, es_id in missing_ids:
            f.write(f"{db_id}, {es_id}\n")
    
    # 2. SQL 복구 스크립트 저장 (DB 원복용)
    sql_filename = f"restore_missing_{timestamp}.sql"
    db_ids_str = ",".join([str(m[0]) for m in missing_ids])
    sql_content = f"""
-- ES에 없는 데이터를 다시 수집 대상으로 변경합니다.
UPDATE article_dataset 
SET content = NULL, crawled_at = NULL, summary_status = NULL 
WHERE id IN ({db_ids_str});
"""
    with open(sql_filename, "w", encoding="utf-8") as f:
        f.write(sql_content)

    print(f"\n✅ 결과 파일 생성 완료:")
    print(f" - 목록 파일: {txt_filename}")
    print(f" - 복구 SQL: {sql_filename}")

def logger_info(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

if __name__ == "__main__":
    from datetime import datetime
    find_missing_docs()

