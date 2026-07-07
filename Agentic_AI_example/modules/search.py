# modules/search.py (전체 코드 업데이트)

import logging
import traceback
import config
from core.llm_client import get_client

# 패키지명 호환성 처리
try:
    from ddgs import DDGS
except ImportError:
    import warnings
    warnings.filterwarnings("ignore", message=".*renamed to `ddgs`.*", category=RuntimeWarning)
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)
client = get_client()

# [수정] 함수명을 run_search로 변경
def run_search(user_input, context_messages=None):
    """
    [SEARCH] 단순 정보/팩트 검색 (문맥 반영)
    """
    
    # 1. 검색어 생성 (문맥 반영)
    yield "🔍 문맥을 파악하여 정보를 찾고 있습니다...\n"
    
    search_query = user_input
    
    # 문맥이 있으면 LLM에게 검색어 생성 요청
    if context_messages:
        system_prompt = """
        You are a Query Refiner.
        Rewrite the user's question into a specific search query for factual information.
        - Resolve pronouns (e.g., "it", "that") using history.
        - Output ONLY the query string.
        """
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(context_messages[-4:])
        messages.append({"role": "user", "content": user_input})

        try:
            resp = client.chat.completions.create(
                model=config.FAST_MODEL_NAME,
                messages=messages, temperature=0
            )
            rewritten = resp.choices[0].message.content.strip().replace('"', '')
            if len(rewritten) < 100:
                search_query = rewritten
                logger.info(f"Query Rewritten: {search_query}")
                yield f"🔍 최적화된 검색어: '{search_query}'\n"
        except:
            pass

    # 2. 검색 수행
    yield f"🌐 웹 검색을 수행합니다... ('{search_query}')\n"
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, region='kr-kr', timelimit='y', max_results=5))
    except Exception as e:
        yield f"❌ 검색 오류: {e}"
        return

    if not results:
        yield "❌ 관련 정보를 찾을 수 없습니다."
        return

    # 3. 답변 생성 (팩트 위주)
    yield "📊 정보를 분석하여 답변을 생성 중입니다...\n\n"
    
    formatted_results = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    
    system_prompt = """
    You are a Fact Search Assistant.
    Answer based on [Search Results].
    - Focus on factual info (specs, price, dates, names).
    - Answer in Korean.
    - Be concise and clear.
    """
    
    try:
        stream = client.chat.completions.create(
            model=config.SMART_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {user_input}\n\nResults:\n{formatted_results}"}
            ],
            stream=True, temperature=0.3
        )
        for chunk in stream:
            if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
            
    except Exception as e:
        yield f"오류 발생: {e}"
