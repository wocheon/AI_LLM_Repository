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

def classify_intent(user_input):
    """[Router] 사용자의 의도를 분류 (CHAT vs DB)"""
    system_prompt = """
    Classify the user input into one of two categories:
    1. 'DB': If the user asks for product information, price, stock, or search (e.g., "맥북 있어?", "비싼 순서대로 보여줘").
    2. 'CHAT': If it is a casual greeting or general conversation (e.g., "안녕", "고마워", "너는 누구니").
    
    Output ONLY the category name ('DB' or 'CHAT'). Do not explain.
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip().upper()
    except Exception:
        return "CHAT" # 에러나면 안전하게 채팅으로

def simple_chat(user_input):
    """[CHAT 모드] 일반 대화 처리"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful shop assistant. Answer kindly in Korean."},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message.content

def generate_sql(user_query, error_msg=None):
    """[SQL 생성] 질문을 SQL로 변환 (에러 메시지가 있으면 참고해서 수정)"""
    schema = get_table_schema()
    
    hint_prompt = ""
    if error_msg:
        hint_prompt = f"\n[Previous Error] The previous query failed with this error: '{error_msg}'. Fix the SQL based on this error."

    system_prompt = f"""
    You are a SQL expert.
    Based on the database schema below, write a MySQL query to answer the user's question.

    [Important Rules]
    1. The product names/brands in the database are in **English** (e.g., 'MacBook Pro', 'Apple').
    2. If the user asks in Korean (e.g., '맥북'), **translate** keywords to English for the query (e.g., LIKE '%MacBook%').
    3. Output **ONLY** the SQL query. No markdown, no explanations.
    4. Do NOT use markdown code blocks (```
    
    [Schema]
    {schema}
    {hint_prompt}
    """

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0 
    )

    #sql = response.choices.message.content.strip()
    sql = response.choices[0].message.content.strip()
    # 마크다운 및 세미콜론 제거 정제
    #sql = re.sub(r'```sql|```')
    sql = re.sub(r'``````', '', sql).strip()
    sql = sql.rstrip(';') 
    return sql

def execute_sql(sql):
    """[SQL 실행] 실제 DB 조회"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            print(f"   [DEBUG] 실행할 쿼리: [{sql}]")
            cursor.execute(sql)
            return cursor.fetchall()

    except Exception as e:
        return f"Error: {e}" # 에러 메시지를 문자열로 반환
    finally:
        if conn: conn.close()

def generate_final_answer(user_query, sql, db_results):
    """[답변 생성] DB 결과를 보고 최종 답변 생성"""

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
        temperature=0.3 
    )
    #return response.choices.message.content
    return response.choices[0].message.content

def run_agent(user_input):
    """[Agent Core] 판단 -> 실행 -> (에러시)수정 -> 응답 Loop"""
    
    # 1. 의도 분류 (Router)
    print("🤔 의도 파악 중...")
    intent = classify_intent(user_input)
    
    if "CHAT" in intent:
        print("   → 일반 대화로 판단")
        return simple_chat(user_input)
    
    print("   → DB 조회 필요")
    
    # 2. SQL 생성 및 실행 (Self-Correction)
    last_error = None
    
    for attempt in range(3): # 최대 3번 시도
        if attempt > 0:
            print(f"🔄 쿼리 수정 시도 ({attempt+1}/3)...")
            
        sql = generate_sql(user_input, error_msg=last_error)
        
        # 안전장치: SELECT 문만 허용
        if not sql.lower().startswith("select"):
            return "⚠️ 안전을 위해 SELECT 쿼리만 허용됩니다."

        result = execute_sql(sql)
        
        # 결과가 에러 문자열인지 확인
        if isinstance(result, str) and result.startswith("Error:"):
            last_error = result
            print(f"   🚨 에러 발생: {last_error}")
            continue # 다음 시도(수정된 SQL 생성)로 넘어감
            
        # 성공 시 답변 생성
        print(f"   → 조회 성공! ({len(result)}건)")
        return generate_final_answer(user_input, sql, result)
        
    return "죄송합니다. 시스템 오류로 데이터를 조회할 수 없습니다."

# --- 메인 실행 ---
def main():
    print("🛒 Agentic 쇼핑몰 AI (Router + Self-Correction) - 종료: quit")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n질문 > ").strip()
        except KeyboardInterrupt:
            break
            
        if not user_input: continue
        if user_input.lower() in ['quit', 'exit']:
            break

        answer = run_agent(user_input)

        print("-" * 60)
        print(f"AI: {answer}")

if __name__ == "__main__":
    main()
