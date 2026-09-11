import pymysql
from openai import OpenAI
import re
import ddgs # 웹 검색용 라이브러리

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
    """[Router] 사용자 의도 분류 (DB / REVIEW / CHAT)"""
    system_prompt = """
    Classify the user input into one of three categories:
    1. 'DB': If asking for internal product info like price, stock, list (e.g., "맥북 재고", "가격 얼마", "삼성 제품 보여줘").
    2. 'REVIEW': If asking for public opinion, news, pros/cons, or latest trends (e.g., "아이폰 15 반응 어때?", "갤럭시 S24 평가", "맥북 단점").
    3. 'CHAT': Casual conversation (e.g., "안녕", "고마워").
    
    Output ONLY the category name ('DB', 'REVIEW', 'CHAT').
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
        return "CHAT"

def simple_chat(user_input):
    """[CHAT] 일반 대화"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful shop assistant. Answer kindly in Korean."},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message.content

# --- 검색(REVIEW) 관련 함수 ---

def search_web(query):
    """[Tool] DuckDuckGo 웹 검색"""
    print(f"   🔎 웹 검색 실행 중: '{query}'...")
    try:
        results = ddgs().text(query, max_results=3)
        summary = ""
        if not results:
            return "검색 결과가 없습니다."
            
        for r in results:
            summary += f"- Title: {r['title']}\n  Content: {r['body']}\n  Link: {r['href']}\n\n"
        return summary
    except Exception as e:
        return f"검색 중 오류 발생: {e}"

def analyze_review(user_input):
    """[REVIEW] 검색 결과 기반 분석 및 요약"""
    
    # 1. 검색 수행 (입력 그대로 사용하거나, 필요시 키워드 추출 로직 추가 가능)
    search_results = search_web(user_input)
    
    # 2. LLM에게 분석 요청
    system_prompt = f"""
    You are a professional Tech Reviewer.
    Based on the [Search Results] below, summarize the public reputation, pros/cons, and key features of the product mentioned in the user's question.
    
    [Instructions]
    1. Answer in Korean.
    2. Structure the answer:
       - **종합 평가 (Summary)**
       - **주요 장점 (Pros)**
       - **주요 단점 (Cons)**
       - **참고 기사 (References)**: List titles from search results.
    
    [Search Results]
    {search_results}
    """
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content

# --- DB(SQL) 관련 함수 ---

def generate_sql(user_query, error_msg=None):
    """[DB] SQL 생성"""
    schema = get_table_schema()
    hint_prompt = f"\n[Previous Error] '{error_msg}'. Fix it." if error_msg else ""

    system_prompt = f"""
    You are a SQL expert.
    Write a MySQL query to answer the user's question based on the schema.

    [Rules]
    1. Product names/brands are in **English** (e.g. 'MacBook', 'Apple'). Translate Korean keywords to English (e.g. '맥북' -> '%MacBook%').
    2. Output **ONLY** the SQL query.
    3. No markdown (```
    
    [Schema]
    {schema}
    {hint_prompt}
    """

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}],
        temperature=0
    )
    sql = response.choices.message.content.strip()
    sql = re.sub(r'``````', '', sql).strip()
    sql = sql.rstrip(';')
    return sql

def execute_sql(sql):
    """[DB] SQL 실행"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            print(f"   [DEBUG] 쿼리 실행: [{sql}]")
            cursor.execute(sql)
            return cursor.fetchall()
    except Exception as e:
        return f"Error: {e}"
    finally:
        if conn: conn.close()

def generate_final_answer_db(user_query, sql, db_results):
    """[DB] 최종 답변 생성 (테이블 포맷)"""
    system_prompt = f"""
    You are a data analyst.
    Answer based on the [Query Result] with a structured table.

    [Rules]
    1. Start with a one-sentence summary in Korean.
    2. Present data in a Markdown Table: | 제품명 | 브랜드 | 카테고리 | 수량 | 가격 |
    3. Format price with commas.
    4. If stock is 0, write "품절".
    5. If empty, say "검색된 제품이 없습니다."

    [User Question] {user_query}
    [Query Result] {db_results}
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "make table"}],
        temperature=0.3
    )
    return response.choices.message.content

# --- 메인 실행 로직 ---

def run_agent(user_input):
    print("🤔 의도 파악 중...", end=" ")
    intent = classify_intent(user_input)
    print(f"→ [{intent}] 모드로 진입")
    
    # 1. 일반 대화
    if "CHAT" in intent:
        return simple_chat(user_input)
    
    # 2. 리뷰/평판 분석 (Web Search)
    elif "REVIEW" in intent:
        return analyze_review(user_input)
        
    # 3. DB 조회 (SQL Agent)
    else: # intent == 'DB'
        last_error = None
        for attempt in range(3):
            if attempt > 0: print(f"🔄 쿼리 수정 중 ({attempt+1}/3)...")
            
            sql = generate_sql(user_input, error_msg=last_error)
            if not sql.lower().startswith("select"): return "⚠️ SELECT 쿼리만 허용됩니다."
            
            result = execute_sql(sql)
            
            if isinstance(result, str) and result.startswith("Error:"):
                last_error = result
                print(f"   🚨 에러: {last_error}")
                continue
                
            return generate_final_answer_db(user_input, sql, result)
            
        return "죄송합니다. 데이터 조회에 실패했습니다."

def main():
    print("🛒 Hybrid AI Agent (DB + Web Search) - 종료: quit")
    print("=" * 60)
    while True:
        try:
            user_input = input("\n질문 > ").strip()
            if not user_input: continue
            if user_input.lower() in ['quit', 'exit']: break
            
            answer = run_agent(user_input)
            print("-" * 60)
            print(f"AI: {answer}")
            
        except KeyboardInterrupt: break
        except Exception as e: print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
