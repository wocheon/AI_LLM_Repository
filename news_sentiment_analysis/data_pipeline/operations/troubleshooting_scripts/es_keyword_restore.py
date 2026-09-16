## Elasticsearch와 MySQL의 target, themes, 감성 분석 결과 동기화 (Full Update)
## ES 문서의 target, themes, 감성 분석 결과가 DB와 일치하지 않는경우, DB 값을 우선시하여 업데이트
## DB -> ES 방향으로 업데이트

import pymysql
import configparser
from elasticsearch import Elasticsearch, helpers
from tqdm import tqdm

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

def sync_db_to_es_full():
    config = get_config()
    
    # ES 설정 파싱
    es_host = config['elasticsearch']['host']
    es_port = config['elasticsearch']['port']
    es_scheme = config['elasticsearch']['scheme']
    es_index = config['elasticsearch']['source_index'] 
    
    es_url = f"{es_scheme}://{es_host}:{es_port}"
    es = Elasticsearch([es_url])
    conn = get_db_conn(config)
    
    print("=== [DB -> ES] Full Metadata 동기화 시작 ===")
    
    try:
        with conn.cursor() as cur:
            # 1. DB 조회: target뿐만 아니라 감성 분석 결과(label_sentiment, confidence)도 가져옴
            print("1. DB 데이터 로드 중...")
            cur.execute("""
                SELECT 
                    content as es_id, 
                    target, 
                    themes, 
                    label_sentiment, 
                    confidence
                FROM article_dataset
                WHERE target IS NOT NULL 
                  AND content IS NOT NULL
                  -- (선택) 감성 분석이 완료된 것만 하려면 아래 조건 추가
                  AND label_sentiment IS NOT NULL 
            """)
            rows = cur.fetchall()
            total_count = len(rows)
            print(f" > 동기화 대상: {total_count}건")

            if total_count == 0:
                print("동기화할 데이터가 없습니다.")
                return

            # 2. Bulk Action 생성 제너레이터 (필드 확장)
            def generate_actions(data_rows):
                for row in data_rows:
                    doc_body = {
                        "target": row['target'],
                        "themes": row['themes']
                    }
                    
                    # 값이 있는 경우에만 doc에 추가 (Null 값 덮어쓰기 방지)
                    if row['label_sentiment'] is not None:
                        doc_body['sentiment_label'] = row['label_sentiment'] # ES 필드명 확인 (sentiment_label)
                    
                    if row['confidence'] is not None:
                        doc_body['confidence'] = row['confidence']

                    yield {
                        "_op_type": "update",
                        "_index": es_index,
                        "_id": row['es_id'],
                        "doc": doc_body
                    }

            # 3. ES Bulk Update 실행
            print("2. ES 업데이트 시작 (Bulk Update)...")
            
            success_count = 0
            error_count = 0
            
            actions = generate_actions(rows)
        
            with tqdm(total=total_count, desc="Syncing") as pbar:
                for ok, info in helpers.streaming_bulk(es, actions, chunk_size=1000, raise_on_error=False):
                    if ok:
                        success_count += 1
                    else:
                        error_count += 1
                    pbar.update(1)

            print("\n=== 동기화 결과 ===")
            print(f"✅ 성공: {success_count}건")
            print(f"❌ 실패: {error_count}건")
            
    except Exception as e:
        print(f"치명적 오류 발생: {e}")
    finally:
        conn.close()
        es.close()

if __name__ == "__main__":
    sync_db_to_es_full()
