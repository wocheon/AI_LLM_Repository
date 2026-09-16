import configparser
import requests
import sys # 로그 강제 출력용
from datetime import datetime
from elasticsearch import Elasticsearch
from db_util import get_db_conn
from sqls import SELECT_ARTICLE_LIST, INSERT_SENTIMENT_RESULT

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    # ES 설정
    es_conf = {
        'host': config['elasticsearch']['host'],
        'port': int(config['elasticsearch']['port']),
        'scheme': config['elasticsearch'].get('scheme', 'http'),
        'user': config['elasticsearch'].get('user'),
        'password': config['elasticsearch'].get('password'),
        'index_name': config['elasticsearch'].get('index_name', 'crawler_articles')
    }

    # API 설정
    api_conf = {
        'model_name': config['api'].get('model_name', 'UnknownModel'),
        'model_version': config['api'].get('model_version', 'v1.0'),
        'url': config['api']['url'],
        'batch_size': int(config['api'].get('batch_size', 32)),
        'max_len': int(config['api'].get('max_length', 512)),
        'is_llm': config['api'].getboolean('is_llm', False) 
    }
    return es_conf, api_conf

def log(msg):
    """로그를 즉시 출력하는 헬퍼 함수"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def analyze_articles():
    es_conf, api_conf = load_config()
    is_llm_mode = api_conf['is_llm']

    log(f">>> Config Loaded: {api_conf['model_name']} (LLM Mode: {is_llm_mode})")

    # ES 연결
    es = Elasticsearch(
        hosts=[{'host': es_conf['host'], 'port': es_conf['port'], 'scheme': es_conf['scheme']}],
        http_auth=(es_conf['user'], es_conf['password']) if es_conf['user'] else None,
    )

    conn = get_db_conn()
    cur = conn.cursor()

    log(">>> Fetching article list from DB...")
    cur.execute(SELECT_ARTICLE_LIST)
    articles = cur.fetchall()
    total_count = len(articles)
    log(f">>> Total articles to process: {total_count}")

    # ==========================================
    # [Case 1] LLM 모드 (한 건씩 처리 + 즉시 Commit)
    # ==========================================
    if is_llm_mode:
        log(">>> Starting Sequential Processing for LLM...")
        
        success_count = 0
        
        for idx, row in enumerate(articles):
            article_id = row[0]
            es_doc_id = row[3]

            try:
                # 1. ES 조회
                try:
                    es_doc = es.get(index=es_conf['index_name'], id=es_doc_id)
                    content = es_doc['_source'].get('content', '')
                except Exception as e:
                    # ES 에러나면 스킵
                    # log(f"[SKIP] ES Error id={article_id}: {e}")
                    continue

                if not content.strip():
                    continue
                
                text_payload = content[:api_conf['max_len']]

                # 2. API 호출
                start = datetime.now()
                # batch 엔드포인트를 쓰더라도 리스트에 1개만 넣어서 보냄
                response = requests.post(api_conf['url'], json={"texts": [text_payload]})
                response.raise_for_status()
                end = datetime.now()
                
                # 결과 파싱
                api_result = response.json()
                # {"model":..., "results": [...]} 형태 가정
                result_data = api_result.get("results", [])[0]
                
                elapsed_ms = int((end - start).total_seconds() * 1000)

                # 3. DB 저장 (한 건마다!)
                cur.execute(INSERT_SENTIMENT_RESULT, (
                    article_id,
                    api_conf['model_name'],
                    api_conf['model_version'],
                    result_data['sentiment'],
                    result_data['score'],
                    elapsed_ms,
                    end
                ))
                
                # [중요] 한 건 할 때마다 커밋해야 DB에서 바로 보임
                conn.commit()
                
                success_count += 1
#                if success_count % 10 == 0:
                log(f"[Progress] {success_count}/{total_count} processed. (Last: {elapsed_ms}ms)")

            except Exception as e:
                # 에러 나도 멈추지 않고 로그 찍고 다음으로
                log(f"[ERROR] id={article_id} failed: {e}")
                conn.rollback() # 에러 난 트랜잭션만 취소

    # ==========================================
    # [Case 2] 일반 모델 (배치 처리 + 배치별 Commit)
    # ==========================================
    else:
        log(">>> Starting Batch Processing...")
        batch_size = api_conf['batch_size']
        
        for i in range(0, total_count, batch_size):
            batch = articles[i : i + batch_size]
            
            article_ids = []
            texts = []
            
            # 데이터 수집
            for row in batch:
                article_id = row[0]
                es_doc_id = row[3]
                try:
                    es_doc = es.get(index=es_conf['index_name'], id=es_doc_id)
                    content = es_doc['_source'].get('summary', '')
                    if content.strip():
                        article_ids.append(article_id)
                        texts.append(content[:api_conf['max_len']])
                except:
                    pass
            
            if not texts: continue

            try:
                # API 호출
                start = datetime.now()
                response = requests.post(api_conf['url'], json={"texts": texts})
                response.raise_for_status()
                end = datetime.now()
                
                predictions = response.json().get("results", [])
                elapsed_ms = int((end - start).total_seconds() * 1000) // len(texts)

                # DB Insert 데이터 준비
                insert_list = []
                for j, pred in enumerate(predictions):
                    insert_list.append((
                        article_ids[j],
                        api_conf['model_name'],
                        api_conf['model_version'],
                        pred['sentiment'],
                        pred['score'],
                        elapsed_ms,
                        end
                    ))
                
                if insert_list:
                    cur.executemany(INSERT_SENTIMENT_RESULT, insert_list)
                    conn.commit() # 배치 단위 커밋
                    log(f"[Batch] {i+len(batch)}/{total_count} done.")
            
            except Exception as e:
                log(f"[ERROR] Batch failed: {e}")
                conn.rollback()

    cur.close()
    conn.close()
    log(">>> Analysis Completed.")

if __name__ == "__main__":
    analyze_articles()

