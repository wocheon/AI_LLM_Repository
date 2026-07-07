import configparser
import requests
from datetime import datetime
from elasticsearch import Elasticsearch
from db_util import get_db_conn
from sqls import SELECT_ARTICLE_LIST, INSERT_SENTIMENT_RESULT

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Elasticsearch 설정
    es_conf = {
        'host': config['elasticsearch']['host'],
        'port': int(config['elasticsearch']['port']),
        'scheme': config['elasticsearch'].get('scheme', 'http'),
        'user': config['elasticsearch'].get('user'),
        'password': config['elasticsearch'].get('password'),
        'index_name': config['elasticsearch'].get('index_name', 'crawler_articles')
    }

    # API 및 배치 설정
    api_conf = {
        'model_name': config['api'].get('model_name', 'UnknownModel'),
        'model_version': config['api'].get('model_version', 'v1.0'),
        'url': config['api']['url'],
        'batch_size': int(config['api'].get('batch_size', 32)),
        'max_len': int(config['api'].get('max_length', 512))
    }

    return es_conf, api_conf

def analyze_articles():
    # 1. 설정 로드
    es_conf, api_conf = load_config()

    print(f">>> Config Loaded:")
    print(f"    - Model: {api_conf['model_name']} ({api_conf['model_version']})")
    print(f"    - URL: {api_conf['url']}")
    print(f"    - Batch Size: {api_conf['batch_size']}")

    # 2. ES 연결
    es = Elasticsearch(
        hosts=[{'host': es_conf['host'], 'port': es_conf['port'], 'scheme': es_conf['scheme']}],
        http_auth=(es_conf['user'], es_conf['password']) if es_conf['user'] else None,
    )

    conn = get_db_conn()
    cur = conn.cursor()

    print(">>> Fetching article list from DB...")
    cur.execute(SELECT_ARTICLE_LIST)
    articles = cur.fetchall()
    total_count = len(articles)
    print(f">>> Total articles to process: {total_count}")

    batch_size = api_conf['batch_size']

    # 3. 배치 루프
    for i in range(0, total_count, batch_size):
        batch = articles[i : i + batch_size]

        article_ids = []
        texts = []

        for row in batch:
            article_id = row[0]
            es_doc_id = row[3] # DB 컬럼 인덱스 확인 필요

            try:
                es_doc = es.get(index=es_conf['index_name'], id=es_doc_id)
                content = es_doc['_source'].get('summary', '')

                if not content.strip():
                    continue

                article_ids.append(article_id)
                # 텍스트 길이 제한 적용
                texts.append(content[:api_conf['max_len']])

            except Exception as e:
                print(f"[WARN] ES fetch failed: id={article_id}, err={e}")

        if not texts:
            continue

        try:
            # 시간 측정 시작
            start_time = datetime.now()

            # API 호출
            response = requests.post(api_conf['url'], json={"texts": texts})
            response.raise_for_status()
            
            # 시간 측정 종료 및 계산
            end_time = datetime.now()
            elapsed_ms = (end_time - start_time).total_seconds() * 1000
            
            # 배치 내 1건당 평균 소요 시간 (반올림)
            avg_inference_ms = int(elapsed_ms / len(texts))
            
            predictions = response.json().get("results", [])

            # DB 저장 데이터 구성
            insert_data_list = []
            
            m_name = api_conf['model_name']
            m_version = api_conf['model_version']

            for j, pred in enumerate(predictions):
                # 튜플 순서: article_id, model_name, model_version, sentiment, score, inference_time_ms, created_at
                insert_data_list.append((
                    article_ids[j],
                    m_name,
                    m_version,
                    pred['sentiment'],
                    pred['score'],
                    avg_inference_ms,  # 계산된 시간 추가
                    end_time
                ))

            if insert_data_list:
                # executemany로 일괄 Insert
                cur.executemany(INSERT_SENTIMENT_RESULT, insert_data_list)
                conn.commit()
                print(f"[Batch {i//batch_size + 1}] Processed {len(insert_data_list)} items. (Avg Time: {avg_inference_ms}ms)")

        except Exception as e:
            print(f"[ERROR] Batch failed: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print(">>> Analysis Completed.")

if __name__ == "__main__":
    analyze_articles()

