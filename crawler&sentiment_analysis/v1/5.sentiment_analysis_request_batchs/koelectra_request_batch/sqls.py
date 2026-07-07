# 모든 기사 SELECT (필요시 조건 추가)
SELECT_ARTICLE_LIST = """
SELECT id, keyword_id, title, content, url, published_at, collected_at 
FROM crawler_article_list;
"""
#WHERE collected_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR);

# 삽입 쿼리 (analyzed_at 칼럼 포함 예시)
INSERT_SENTIMENT_RESULT = """
    INSERT INTO sentiment_results 
    (article_id, model_name, model_version, sentiment, score, inference_time_ms, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        sentiment = VALUES(sentiment),
        score = VALUES(score),
        inference_time_ms = VALUES(inference_time_ms),
        created_at = VALUES(created_at)
"""


#INSERT_SENTIMENT_RESULT = """
#INSERT INTO koelectra_sentiment_analysis_result 
#(article_id, sentiment, score, analyzed_at)
#VALUES (%s, %s, %s, %s)
#"""
