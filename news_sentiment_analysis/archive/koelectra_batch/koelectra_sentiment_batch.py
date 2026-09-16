import configparser
from elasticsearch import Elasticsearch
from transformers import AutoTokenizer, ElectraForSequenceClassification
import torch
from db_util import get_db_conn
from sqls import SELECT_ARTICLE_LIST, INSERT_SENTIMENT_RESULT
from datetime import datetime

LABEL_MAP = {
    0: "angry",
    1: "happy",
    2: "anxious",
    3: "embarrassed",
    4: "sad",
    5: "heartache"
}

KOELECTRA_MODEL_DIR = "/models/koelectra"

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

def load_koelectra_model():
    tokenizer = AutoTokenizer.from_pretrained(KOELECTRA_MODEL_DIR)
    model = ElectraForSequenceClassification.from_pretrained(KOELECTRA_MODEL_DIR)
    model.eval()
    return tokenizer, model

def predict_sentiment_koelectra(tokenizer, model, text):
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

    tokenizer, model = load_koelectra_model()

    for article in articles:
        # article = (id, keyword_id, title, content, url, published_at, collected_at)
        article_id = article[0]
        es_doc_id = article[3]     # content에 ES 문서 id가 들어있음
        try:
            # Elasticsearch에서 기사 본문(content) 추출
            es_doc = es.get(index=index_name, id=es_doc_id)
            full_content = es_doc['_source'].get('content', '')

            sentiment, score = predict_sentiment_koelectra(tokenizer, model, full_content)

            # 결과 DB 저장 (필요시 analyzed_at 등도 추가)
            cur.execute(
                INSERT_SENTIMENT_RESULT,
                (article_id, sentiment, score, datetime.now()) # analyzed_at이 필요하다면
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

