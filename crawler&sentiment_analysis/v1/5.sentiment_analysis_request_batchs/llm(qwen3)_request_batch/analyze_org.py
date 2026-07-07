import configparser
import requests
from datetime import datetime
from elasticsearch import Elasticsearch
from db_util import get_db_conn
from sqls import SELECT_ARTICLE_LIST, INSERT_SENTIMENT_RESULT

API_URL = "http://sentiment_model_fastapi:8000/predict/kobert"  # 모델 API 서버 주소

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    host = config['elasticsearch']['host']
    port = int(config['elasticsearch']['port'])
    scheme = config['elasticsearch'].get('scheme', 'http')
    user = config['elasticsearch'].get('user')
    password = config['elasticsearch'].get('password')
    index_name = config['elasticsearch'].get('index_name', 'crawler_articles')
    return host, port, scheme, user, password, index_name


def analyze_articles():
    host, port, scheme, user, password, index_name = load_config()
    es = Elasticsearch(
        hosts=[{'host': host, 'port': port, 'scheme': scheme}],
        http_auth=(user, password) if user and password else None,
    )

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(SELECT_ARTICLE_LIST)
    articles = cur.fetchall()

    for article in articles:
        article_id = article[0]
        es_doc_id = article[3]  # DB에서 Elasticsearch 문서 ID 가져오기 (배열 순서 맞게 조정하세요)
        
        try:
            # Elasticsearch에서 기사 본문 조회
            es_doc = es.get(index="crawler_articles", id=es_doc_id)
            content = es_doc['_source'].get('content', '')

            # 감성 분석 API 호출
            response = requests.post(API_URL, json={"text": content})
            response.raise_for_status()
            result = response.json()

            sentiment = result.get("sentiment")
            score = result.get("score")

            # 결과 DB 저장
            cur.execute(
                INSERT_SENTIMENT_RESULT,
                (article_id, sentiment, score, datetime.now())
            )

            print(f"[OK] 기사id={article_id}, sentiment={sentiment}, score={score}")

        except Exception as e:
            print(f"[ERROR] 기사id={article_id} 분석 실패: {e}")

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    analyze_articles()

