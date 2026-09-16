# Elasticsearch와 MySQL의 summary_status 무결성 검사 및 복구 
# ES 문서의 summary 필드가 비어있는 경우, DB의 summary_status가 'COMPLETED'인 경우를 찾아
# 해당 건들을 '재작업 대기' 상태로 변경

import pymysql
import configparser
from elasticsearch import Elasticsearch

def get_config(path="config.ini"):
    config = configparser.ConfigParser()
    config.read(path, encoding='utf-8')
    return config

def get_db_conn(config):
    db_cfg = config['mysql']
    return pymysql.connect(
        host=db_cfg['host'],
        user=db_cfg['user'],
        password=db_cfg['password'],
        db=db_cfg['database'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def dry_run_fix_inconsistency():
    config = get_config()
    
    # [elasticsearch] 설정 파싱
    es_host = config['elasticsearch']['host']
    es_port = config['elasticsearch']['port']
    es_scheme = config['elasticsearch']['scheme']
    es_index = config['elasticsearch']['source_index']
    
    es_url = f"{es_scheme}://{es_host}:{es_port}"
    es = Elasticsearch([es_url])
    
    conn = get_db_conn(config)
    batch_size = 1000
    inconsistent_ids = []

    print(f"[{es_index}] 인덱스와 DB 간 무결성 검사 시작 (Dry-Run)...")

    try:
        with conn.cursor() as cur:
            # 1. DB에서 '완료' 상태 조회
            cur.execute(f"""
                SELECT id, content as es_id 
                FROM article_dataset 
                WHERE summary_status = 'COMPLETED' 
                  AND content IS NOT NULL
            """)
            db_rows = cur.fetchall()
            total = len(db_rows)
            print(f" > DB 검사 대상: 총 {total}건")

            # 2. ES 데이터 검증
            for i in range(0, total, batch_size):
                batch = db_rows[i:i+batch_size]
                es_ids = [row['es_id'] for row in batch]

                # mget으로 요약 필드 확인
                resp = es.mget(index=es_index, ids=es_ids, _source=["summary"])
                
                es_data_map = {}
                for doc in resp['docs']:
                    if doc.get('found'):
                        summary_val = doc.get('_source', {}).get('summary')
                        es_data_map[doc['_id']] = summary_val
                    else:
                        es_data_map[doc['_id']] = None # 문서 없음

                # 불일치 식별
                for row in batch:
                    es_val = es_data_map.get(row['es_id'])
                    # ES에 값이 없거나 빈 문자열이면 불일치
                    if not es_val or str(es_val).strip() == "":
                        inconsistent_ids.append(row['id'])

                print(f" > 진행률: {min(i+batch_size, total)}/{total} (발견된 불일치: {len(inconsistent_ids)}건)")

            # 3. 복구용 쿼리 출력 (실행 X)
            if inconsistent_ids:
                print("\n" + "="*50)
                print(f"🚨 불일치 데이터 발견: {len(inconsistent_ids)}건")
                print("아래 쿼리를 실행하면 해당 건들을 '재작업 대기' 상태로 되돌립니다.")
                print("="*50 + "\n")
                
                # ID 목록을 콤마로 연결
                ids_str = ",".join(map(str, inconsistent_ids))
                
                sql_query = f"""
                UPDATE article_dataset 
                SET summary_status = NULL
                WHERE id IN ({ids_str});
                """
                
                print(sql_query)
                
                # 파일로도 저장 (ID가 많을 경우 콘솔 복사가 힘들 수 있음)
                with open("fix_summary_inconsistency.sql", "w", encoding="utf-8") as f:
                    f.write(sql_query)
                print(f"\n[INFO] 위 쿼리는 'fix_summary_inconsistency.sql' 파일로도 저장되었습니다.")

            else:
                print("\n✅ 데이터가 완벽하게 동기화되어 있습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        conn.close()
        es.close()

if __name__ == "__main__":
    dry_run_fix_inconsistency()
