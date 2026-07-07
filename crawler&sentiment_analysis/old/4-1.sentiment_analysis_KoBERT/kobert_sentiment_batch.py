# kobert_sentiment_batch.py
import configparser
from elasticsearch import Elasticsearch
from transformers import AutoTokenizer, BertForSequenceClassification
import torch
from db_util import get_db_conn
from sqls import SELECT_ARTICLE_LIST, INSERT_SENTIMENT_RESULT
from datetime import datetime

LABEL_MAP = {
    0: "Angry",
    1: "Fear",
    2: "Happy",
    3: "Tender",
    4: "Sad"
}

KOBERT_MODEL_DIR = "/models/kobert"

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

def load_kobert_model():
    tokenizer = AutoTokenizer.from_pretrained(KOBERT_MODEL_DIR)
    model = BertForSequenceClassification.from_pretrained(KOBERT_MODEL_DIR)
    model.eval()
    return tokenizer, model

def predict_sentiment_kobert(tokenizer, model, text):
    if not text:
        return None, None
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=256,
        padding=True
    )
    with torch.no_grad():
        outputs = model(**inputs)
        prob = torch.softmax(outputs.logits, dim=1)
        pred_label = torch.argmax(prob, dim=1).item()
        score = float(prob[0][pred_label])
    sentiment = LABEL_MAP.get(pred_label, str(pred_label))
    return sentiment, score

def main():
    host, port, scheme, user, password, index_name = load_config()
    es = Elasticsearch(
        hosts=[{'host': host, 'port': port, 'scheme': scheme}],
        http_auth=(user, password) if user and password else None,
    )

    # DB 연결 및 기사 목록 조회
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(SELECT_ARTICLE_LIST)
    articles = cur.fetchall()

    tokenizer, model = load_kobert_model()

    for article in articles:
        # article = (id, keyword_id, title, content, url, published_at, collected_at)
        article_id = article[0]
        es_doc_id = article[3]  # content 칼럼에 ES 문서 ID가 저장되어 있다고 가정
        try:
            # Elasticsearch에서 기사 본문(content) 추출
            es_doc = es.get(index=index_name, id=es_doc_id)
            full_content = es_doc['_source'].get('content', '')

            sentiment, score = predict_sentiment_kobert(tokenizer, model, full_content)

            # 결과 DB 저장
            cur.execute(
                INSERT_SENTIMENT_RESULT,
                (article_id, sentiment, score, datetime.now())  # analyzed_at 포함
            )

            print(f"[OK] 기사id={article_id}, ES-ID={es_doc_id}, sentiment={sentiment}, score={score}")

        except Exception as e:
            print(f"[ERROR] 기사 {article_id} (ES-ID={es_doc_id}) 분석실패: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"[INFO] 분석 및 저장 완료")

if __name__ == "__main__":
    main()

