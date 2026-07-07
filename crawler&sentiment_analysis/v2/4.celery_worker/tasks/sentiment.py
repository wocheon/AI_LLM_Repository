import logging
import requests
import time
from datetime import datetime
from celery import shared_task
from utils.db_client import get_db_conn
from utils.config_loader import config_loader

logger = logging.getLogger(__name__)

# [기본 설정 로드]
try:
    default_conf = config_loader.get_section('api')
    DEFAULT_API_URL = default_conf.get('url')
    DEFAULT_MODEL_NAME = default_conf.get('model_name', 'KoBERT-Senti5')
    DEFAULT_MODEL_VERSION = default_conf.get('model_version', 'v1.0')
except Exception:
    DEFAULT_API_URL = None
    DEFAULT_MODEL_NAME = 'Unknown'
    DEFAULT_MODEL_VERSION = 'v0.0'

def get_db_article_id(es_doc_id):
    """ES ID로 DB Integer ID 조회"""
    conn = None
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        sql = "SELECT id FROM crawler_article_list WHERE content = %s LIMIT 1"
        cursor.execute(sql, (es_doc_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"DB Lookup Failed: {e}")
        return None
    finally:
        if conn: conn.close()

@shared_task(name='tasks.sentiment.analyze_sentiment', bind=True, max_retries=3)
def analyze_sentiment(self, data, model_info=None):
    """
    data: Summary 태스크의 결과 (dict)
    model_info: Collector에서 전달한 모델 설정 (dict)
    """
    # 1. 데이터 검증
    if not data:
        return "Skipped (No Data)"
        
    if isinstance(data, str):
        logger.error(f"[Sentiment] Invalid input (str): {data}")
        return f"Failed (Invalid Input: {data})"

    # 2. 설정 결정 (전달받은 값 우선)
    if model_info:
        api_url = model_info.get('api_url', DEFAULT_API_URL)
        model_name = model_info.get('model_name', DEFAULT_MODEL_NAME)
        model_version = model_info.get('model_version', DEFAULT_MODEL_VERSION)
    else:
        api_url = DEFAULT_API_URL
        model_name = DEFAULT_MODEL_NAME
        model_version = DEFAULT_MODEL_VERSION

    if not api_url:
        logger.error("API URL is missing.")
        return "Failed (Config Error)"

    # 3. 데이터 파싱
    es_doc_id = data.get('id')
    summary_text = data.get('summary')

    if not summary_text:
        return "Skipped (No Summary)"

    # 4. DB ID 조회
    db_article_id = get_db_article_id(es_doc_id)
    if not db_article_id:
        logger.error(f"DB ID not found for ES ID: {es_doc_id}")
        return "Failed (DB ID Not Found)"

    logger.info(f"[Sentiment] Analyzing {db_article_id} with {model_name}...")

    try:
        # 5. API 호출
        payload = {"texts": [summary_text]}
        
        start_time = time.time()
        response = requests.post(api_url, json=payload, timeout=20)
        end_time = time.time()
        
        inference_time_ms = int((end_time - start_time) * 1000)
        response.raise_for_status()
        
        results = response.json().get('results', [])
        if not results:
            return "No Result"

        prediction = results[0]
        sentiment = prediction.get('sentiment')
        score = prediction.get('score', 0.0)

        # 6. DB 저장
        conn = get_db_conn()
        cursor = conn.cursor()
        
        sql = """
            INSERT INTO sentiment_results 
            (article_id, model_name, model_version, sentiment, score, inference_time_ms, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                sentiment = VALUES(sentiment),
                score = VALUES(score),
                inference_time_ms = VALUES(inference_time_ms),
                created_at = VALUES(created_at)
        """
        vals = (db_article_id, model_name, model_version, sentiment, score, inference_time_ms, datetime.now())
        
        cursor.execute(sql, vals)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        logger.info(f"[Sentiment] Saved {model_name}: {sentiment} ({score:.2f})")
        return f"Success: {model_name}"

    except Exception as e:
        logger.error(f"[Sentiment] Error ({model_name}): {e}")
        raise self.retry(exc=e, countdown=60)
