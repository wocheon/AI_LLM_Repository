# sqls.py

SELECT_ALL_KEYWORDS = """
    SELECT id, keyword FROM crawler_keyword_list order by id;
"""

INSERT_ARTICLE = """
    INSERT INTO crawler_article_list (keyword_id, title, content, url, published_at)
    VALUES (%s, %s, %s, %s, %s);
"""
