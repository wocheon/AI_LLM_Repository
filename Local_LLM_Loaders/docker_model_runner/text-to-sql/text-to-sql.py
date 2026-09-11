import pymysql
from openai import OpenAI
import re

# --- 설정 ---
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'CHANGE_ME_ROOT_PASSWORD',
    'db': 'shop',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

DMR_BASE_URL = "http://localhost:12434/engines/llama.cpp/v1"
DMR_API_KEY = "ollama"
MODEL_NAME = "ai/qwen3:4B-UD-Q8_K_XL"

client = OpenAI(base_url=DMR_BASE_URL, api_key=DMR_API_KEY)

# --- 함수 정의 ---

def get_table_schema():
    """AI에게 테이블 구조를 알려주기 위한 스키마 정의"""
    return """
Table: products
Columns:
- id (INT)
- name (VARCHAR): 상품명 (예: MacBook Pro, Galaxy S24)
- brand (VARCHAR): 브랜드명 (예: Apple, Samsung)
- category (VARCHAR): 카테고리 (예: PC, Smartphone)
- stock (INT): 재고 수량
- price (INT): 가격
"""


def generate_sql(user_query):
    """AI에게 질문을 SQL로 바꿔달라고 요청 (1단계)"""
    schema = get_table_schema()
    system_prompt = f"""
    You are a SQL expert. 
    Based on the database schema below, write a MySQL query to answer the user's question.
    
    [Important Rules]
    1. The product names in the database are in **English** (e.g., 'MacBook Pro', 'iPhone 15').
    2. If the user asks in Korean (e.g., '맥북'), you must **translate** the keyword to English for the SQL query (e.g., WHERE name LIKE '%MacBook%').
    3. Output ONLY the SQL query.
    
    [Schema]
    {schema}
    """
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0 # SQL은 정확해야 하므로 창의성 낮춤
    )
    
    # AI가 `````` 같은 마크다운을 쓸 수 있으니 제거
    sql = response.choices[0].message.content.strip()
    sql = re.sub(r'``````', '', sql).strip() 
    return sql

def execute_sql(sql):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # 2. 실제 쿼리 실행
            print(f"   [DEBUG] 실행할 쿼리: [{sql}]")
            cursor.execute(sql)
            return cursor.fetchall()
            
    except Exception as e:
        return f"Error: {e}"
    finally:
        if conn: conn.close()

def generate_final_answer(user_query, sql, db_results):
    """DB 결과와 질문을 합쳐서 최종 답변 생성 (2단계)"""
    
    system_prompt = f"""
    You are a helpful data analyst assistant.
    The user asked a question about products, and we retrieved the data from the database.
    
    [Goal]
    Answer the user's question based on the [Query Result] with a brief explanation followed by a structured table.
    
    [Strict Output Rules]
    1. Start with a concise **one-sentence summary** in Korean based on the search result.
       - Example: "요청하신 '맥북' 관련 제품의 재고 현황입니다."
    2. Leave one blank line.
    3. Present the data in a **Markdown Table** with these columns:
       | 제품명 | 브랜드 | 카테고리 | 수량 | 가격 |
    4. Format the '가격' column with commas (e.g., 3,500,000원).
    5. If stock is 0, show "품절" instead of the number.
    6. If [Query Result] is empty, just say "검색된 제품이 없습니다."
    
    [User Question] {user_query}
    [Executed SQL] {sql}
    [Query Result] {db_results}
    """
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "결과를 요약하고 표를 만들어줘."}
        ],
        temperature=0.3 # 자연스러운 문장을 위해 온도를 살짝 올림
    )
    return response.choices[0].message.content


# --- 메인 실행 ---
def main():
    print("🛒 똑똑한 쇼핑몰 AI (Text-to-SQL) - 종료: quit")
    print("=" * 50)

    while True:
        user_input = input("\n질문 > ").strip()
        if user_input.lower() in ['quit', 'exit']:
            break
            
        print(f"🤔 SQL 생성 중...")
        sql = generate_sql(user_input)
        print(f"   → 생성된 SQL: {sql}")
        
        # 안전장치: SELECT 문만 실행하도록 제한 (삭제 방지)
        if not sql.lower().startswith("select"):
            print("⚠️ 안전을 위해 SELECT 쿼리만 허용됩니다.")
            continue

        print(f"🔍 DB 조회 중...")
        results = execute_sql(sql)
        print(f"   → 조회 결과: {results}")
        
        print(f"🤖 최종 답변 생성 중...")
        answer = generate_final_answer(user_input, sql, results)
        
        print("-" * 50)
        print(f"AI: {answer}")

if __name__ == "__main__":
    main()
