# sqls_dataset.py

# 1. 작업 대상 선점 (MariaDB/MySQL 병렬 처리용)
UPDATE_PICK_TARGETS = """
    UPDATE article_dataset 
    SET content = %s 
    WHERE id IN (
        SELECT id FROM (
            SELECT id FROM article_dataset 
            WHERE (content IS NULL OR content = '' OR content = '[no_es_id]')
            ORDER BY id DESC 
            LIMIT 5000
        ) AS temp
    )
"""


# 2. 내가 선점한 대상만 정확히 조회
# 다른 컨테이너가 'PROCESSING'으로 바꾼 것은 건드리지 않습니다.
SELECT_PICKED_TARGETS = """
    SELECT id, url, title, published_at, section, target, themes
    FROM article_dataset 
    WHERE content = %s
"""

# 3. 수집 성공 시 최종 업데이트 (ES ID, 정제된 URL, 크롤링 시간 반영)
UPDATE_COLLECT_SUCCESS = """
    UPDATE article_dataset 
    SET content = %s, url = %s, crawled_at = %s 
    WHERE id = %s
"""

# 4. 수집 실패 시 에러 처리
UPDATE_COLLECT_ERROR = """
    UPDATE article_dataset 
    SET content = 'ERROR' 
    WHERE id = %s
"""

