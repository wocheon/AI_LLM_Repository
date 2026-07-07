# src/resources/queries.py

class SummarySQL:
    SELECT_TARGET_BATCH = """
        SELECT id, content as es_id 
        FROM article_dataset 
        WHERE content IS NOT NULL 
        AND content != 'ERROR' 
        AND content NOT LIKE 'worker_%%'
        AND (summary_status IS NULL OR summary_status = '' OR summary_status = 'PENDING')
        LIMIT %s
    """
    SELECT_TARGET_SINGLE = """
        SELECT id, content as es_id 
        FROM article_dataset 
        WHERE id = %s
    """
    UPDATE_COMPLETED = """
        UPDATE article_dataset 
        SET summary_status='COMPLETED'
        WHERE id=%s
    """
    UPDATE_ERROR = "UPDATE article_dataset SET summary_status='ERROR' WHERE id=%s"

class LabelerSQL:
    SELECT_TARGET_BATCH = """
        SELECT id, title, content as es_id 
        FROM article_dataset
        WHERE label_sentiment IS NULL AND summary_status = 'COMPLETED'
        LIMIT %s
    """
    SELECT_TARGET_SINGLE = """
        SELECT id, title, content as es_id 
        FROM article_dataset 
        WHERE id = %s
    """
    UPDATE_RESULT = """
        UPDATE article_dataset
        SET target=%s, themes=%s, label_sentiment=%s, confidence=%s, embedding_status='PENDING'
        WHERE id=%s
    """
    CHECK_REMAINING = """
        SELECT COUNT(*) as cnt 
        FROM article_dataset 
        WHERE label_sentiment IS NULL AND summary_status = 'COMPLETED'
    """

class EmbedderSQL:
    # [수정] target, themes 컬럼 추가
    SELECT_TARGET_BATCH = """
        SELECT id, title, target, themes, content as es_id 
        FROM article_dataset
        WHERE embedding_status = 'PENDING' AND summary_status = 'COMPLETED'
        LIMIT %s
    """
    
    # [수정] target, themes 컬럼 추가
    SELECT_TARGET_SINGLE = """
        SELECT id, title, target, themes, content as es_id 
        FROM article_dataset 
        WHERE id = %s
    """
    UPDATE_STATUS = "UPDATE article_dataset SET embedding_status = 'COMPLETED' WHERE id = %s"
