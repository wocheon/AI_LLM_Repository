# modules/db.py
import pymysql
import re
import logging
import config
from core.llm_client import get_client

logger = logging.getLogger(__name__)
client = get_client()

def get_table_schema():
    """스키마 정보 (재고 + 매출 테이블)"""
    return """
    Table: products (Current Stock & Info)
    - id (INT)
    - name (VARCHAR): English Name (e.g., 'Galaxy Buds3')
    - kor_name (VARCHAR): Korean Name (e.g., '갤럭시 버즈3')
    - brand (VARCHAR)
    - category (VARCHAR)
    - stock (INT): Current quantity
    - price (INT): Unit price

    Table: sales (Sales History)
    - id (INT)
    - product_id (INT): Foreign Key -> products.id
    - quantity (INT): Sold count
    - total_price (INT): Revenue (price * quantity)
    - sold_at (TIMESTAMP): Sales time (e.g., '2024-01-01 12:00:00')

    [Relationships]
    - sales.product_id = products.id
    """

def clean_sql(sql_text):
    """SQL 정제 헬퍼"""
    # 1. 마크다운 코드 블록 제거 (SyntaxError 방지: 문자열 연산 사용)
    backticks = "`" * 3
    pattern = r"({})(?:sql)?(.*?)(\1)".format(backticks)
    
    match = re.search(pattern, sql_text, re.DOTALL)
    if match:
        sql_text = match.group(2)
    else:
        sql_text = sql_text.replace(backticks, "")

    # 2. 앞뒤 공백, 세미콜론 제거
    sql_text = sql_text.strip().rstrip(';')
    
    # 3. 한 줄로 만들기
    sql_text = " ".join(sql_text.split())
    
    return sql_text

def generate_sql(user_query, chat_history=None, error_msg=None):
    """SQL 생성 (Context Aware & Explicit Column Selection)"""
    hint = f"\n[Fix Error] {error_msg}" if error_msg else ""
    
    # 1. [Context] 대화 문맥 포맷팅
    context_text = "No previous context."
    if chat_history:
        recent_history = chat_history[-2:] 
        context_text = "\n".join([f"User: {msg['user']}\nAI: {msg['assistant']}" for msg in recent_history])

    # 2. [Intent] 의도 파악
    history_keywords = ['이력', '기록', '언제', '내역', '날짜', 'history', 'log', 'when', 'date']
    is_history_query = any(k in user_query for k in history_keywords)

    # 3. [Mode] 모드별 지침 (필수 컬럼 명시)
    if is_history_query:
        mode_instruction = """
        [MODE: DAILY SALES HISTORY]
        - User wants sales records per date.
        - **[CRITICAL] USE LEFT JOIN**: `FROM products p LEFT JOIN sales s ON p.id = s.product_id`
        - **SELECT Columns**: 
          1. `DATE_FORMAT(s.sold_at, '%Y-%m-%d %H:%i')`
          2. `p.kor_name`
          3. `IFNULL(s.quantity, 0)`
          4. `IFNULL(s.total_price, 0)`
        - **Date Filter**: Put date logic in `ON` clause (e.g., `ON ... AND s.sold_at >= ...`) to keep unsold items.
        - ORDER BY `s.sold_at` DESC LIMIT 20
        """
    else:
        mode_instruction = """
        [MODE: STOCK INFO / GENERAL]
        - User wants current stock, price, or general info.
        - **SELECT Columns (MUST include ALL)**: 
          1. `p.brand`
          2. `p.category`
          3. `p.kor_name`
          4. `p.name`
          5. `p.stock`
          6. `p.price`
        - FROM `products` table.
        """

    system_prompt = f"""
    You are a SQL expert for 'shop' DB.
    
    [Schema]
    {get_table_schema()}
    
    [Context Handling]
    - **Current User Query**: "{user_query}"
    - **Previous Conversation**:
    {context_text}
    - **Instruction**: If the user uses pronouns like "that", "it", "저거", "그거", refer to the **Product Name** mentioned in the [Previous Conversation].
    - **Example**: If previous was about 'Galaxy Buds', and user asks "Stock for that?", search for 'Galaxy Buds'.

    [Instructions]
    {mode_instruction}
    
    [Rules]
    1. **Search Logic**:
       - Split keywords (e.g. "Buds3 Pro" -> `%Buds%` AND `%3%` AND `%Pro%`).
       - Apply to BOTH `p.name` OR `p.kor_name`.
    
    2. **Date Logic**:
       - 'Today': `CURDATE()`
       - 'This Month': `DATE_FORMAT(NOW(), '%Y-%m-01')`
    
    3. **Output**: ONLY the SQL string starting with SELECT.
    
    {hint}
    """
    
    try:
        response = client.chat.completions.create(
            model=config.FAST_MODEL_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}],
            temperature=0
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        sql = clean_sql(raw_response)
        logger.info(f"Generated SQL: {sql}")
        return sql
        
    except Exception as e:
        logger.error(f"SQL Gen Failed: {e}")
        return "SELECT 1"

def execute_sql(sql):
    """SQL 실행"""
    conn = None
    try:
        conn = pymysql.connect(**config.DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
            return result if result else []
    except Exception as e:
        return f"Error: {e}"
    finally:
        if conn: conn.close()

def format_db_answer_stream(user_query, db_results):
    """DB 결과를 스트리밍으로 포맷팅"""
    
    if not db_results or db_results == ():
        yield "조회하신 조건에 맞는 데이터가 없거나, 판매 이력이 존재하지 않습니다."
        return

    prompt = f"""
    Summarize the DB result in Korean based on [Data].
    
    [Data]: {db_results}
    
    [Rules]
    1. **Summary**: Start with a 1-sentence summary (e.g., "현재 'OOO' 제품의 재고는 X개입니다.").
    
    2. **Dynamic Table**:
       - **CASE A (Sales History)**: If data has dates ('2024-..'):
         | 판매일시 | 제품명 | 수량 | 결제금액 |
         
       - **CASE B (Stock/Info)**: If data has brand/category/price:
         | 브랜드 | 카테고리 | 제품명(한글) | 재고 | 가격 |
       
    3. **Formatting**:
       - Format price with commas (e.g., "240,000원").
       - If stock is 0, write "품절".
       - Include ALL rows.
    """
    
    try:
        stream = client.chat.completions.create(
            model=config.SMART_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}], 
            temperature=0.3,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
    except Exception as e:
        logger.error(f"Format Error: {e}")
        yield str(db_results)

def run_db_agent(user_input, chat_history=None):
    """[Generator] DB 에이전트 메인"""
    last_error = None
    for attempt in range(3):
        sql = generate_sql(user_input, chat_history, last_error)
        
        if not sql.lower().startswith("select"):
            logger.warning(f"Invalid SQL: {sql}")
            if attempt == 2:
                yield "⚠️ SQL 생성 오류: 올바른 쿼리를 생성하지 못했습니다."
                return
            continue 
            
        result = execute_sql(sql)
        
        if isinstance(result, str) and result.startswith("Error:"):
            last_error = result
            logger.warning(f"SQL Exec Error: {result}")
            continue
            
        yield from format_db_answer_stream(user_input, result)
        return
    
    yield "❌ 데이터 조회 실패 (시스템 오류)"
