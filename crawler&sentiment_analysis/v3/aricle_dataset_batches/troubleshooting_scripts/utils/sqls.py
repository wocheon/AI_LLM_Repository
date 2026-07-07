# sqls_dataset.py

# 대상 조회 SQL
SELECT_PICKED_TARGETS = """
SELECT id, content FROM article_dataset WHERE content IS NOT NULL AND content != 'ERROR' AND content not like 'worker_%' AND summary_status IS NULL LIMIT {limit}
"""

# 요약 완료 상태 업데이트 SQL
UPDATE_SUMMARY_COMPLETED = """
UPDATE article_dataset SET summary_status = 'COMPLETED' WHERE id = %s
"""

# 요약 실패 상태 업데이트 SQL
UPDATE_SUMMARY_ERROR = """
UPDATE article_dataset SET summary_status = 'ERROR' WHERE id = %s
"""

