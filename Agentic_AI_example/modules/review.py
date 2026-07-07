# modules/review.py
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

def run_review(user_input, context_messages=None):
    """
    [REVIEW] 심층 분석/평가 (문맥 반영)
    :param user_input: 사용자 질문 (예: "저 제품 어때?", "A랑 B 비교해줘")
    :param context_messages: 이전 대화 기록 (대명사 해결용)
    """
    
    # 1. 검색어 생성 (항상 최적화 시도)
    yield "📝 질문을 분석하여 최적의 검색어를 생성 중입니다...\n"

    # 기본값
    search_query = user_input
    
    # [수정] 무조건 Rewrite 로직 실행
    system_prompt_rewrite = """
    You are a Query Refiner.
    Rewrite the user's question into a specific search query for a search engine.
    
    [Rules]
    1. Look at the conversation history (if any) to resolve pronouns like "it", "that", "저거".
    2. **If Comparison (e.g., "비교", "vs", "차이"):** Generate "Product A vs Product B comparison review".
    3. **If Single Product:** Add keywords like 'review', 'pros cons', 'rating'.
    4. Remove unnecessary words ("알려줘", "어때", "궁금해").
    5. Output **ONLY** the search query string.
    """

    messages = [{"role": "system", "content": system_prompt_rewrite}]
    
    # 이전 대화가 있으면 추가
    if context_messages:
        messages.extend(context_messages[-4:]) 
    
    messages.append({"role": "user", "content": user_input})

    try:
        # Fast Model 사용
        resp = client.chat.completions.create(
            model=config.FAST_MODEL_NAME,
            messages=messages,
            temperature=0
        )
        rewritten = resp.choices[0].message.content.strip().replace('"', '')
        
        # 결과 검증 (너무 길거나 이상하면 원본 사용)
        if len(rewritten) < 100:
            search_query = rewritten
            logger.info(f"Query Rewritten: '{user_input}' -> '{search_query}'")
            yield f"🔍 최적화된 검색어: '{search_query}'\n"
        else:
            # 실패 시 안전한 기본값
            search_query = f"{user_input} review"
            
    except Exception as e:
        logger.error(f"Query Rewrite Failed: {e}")
        search_query = f"{user_input} review"

    # 2. 웹 검색 수행
    yield f"🌐 웹 검색을 수행합니다... ('{search_query}')\n"
    
    try:
        with DDGS() as ddgs:
            # 리뷰는 최신 정보가 중요하므로 timelimit='y'
            results = list(ddgs.text(search_query, region='kr-kr', timelimit='y', max_results=5))
    except Exception as e:
        logger.error(f"Search Error: {traceback.format_exc()}")
        yield f"❌ 검색 시스템 오류: {e}"
        return

    if not results:
        yield "❌ 관련 리뷰를 찾을 수 없습니다. 검색어를 변경해 보세요."
        return

    # 3. LLM 분석 및 답변 생성 (스트리밍)
    yield "📊 검색 결과를 분석하여 요약 중입니다...\n\n"

    # 검색 결과 리스트 -> 문자열 변환
    formatted_results = ""
    for r in results:
        formatted_results += f"- Title: {r.get('title')}\n  Body: {r.get('body')}\n\n"

    system_prompt_analyze = f"""
    You are a Tech Review Expert.
    Analyze the [Search Results] to answer the user's question.
    
    [Instructions]
    1. Answer in Korean.
    
    2. **[Scenario A] If the user asks for a COMPARISON ("비교", "vs"):**
       - **비교 요약**: One paragraph summarizing the key differences.
       - **상세 비교 (Table/List)**: Compare Specs, Price, Performance, Features.
       - **추천 (Verdict)**: Which one is better for whom? (e.g., "For gamers, A is better.")
    
    3. **[Scenario B] If the user asks for a SINGLE PRODUCT REVIEW:**
       - **요약 (Summary)**: Overall reputation.
       - **장점 (Pros)**: Key strengths.
       - **단점 (Cons)**: Key weaknesses.
    
    4. Be objective and cite sources.
    5. **[IMPORTANT] If results are empty, output "충분한 정보를 찾지 못했습니다." ONLY. Do not use this phrase if you found info.**
    
    [Search Results]
    {formatted_results}
    """
    
    try:
        stream = client.chat.completions.create(
            model=config.SMART_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt_analyze},
                {"role": "user", "content": f"Question: {user_input}\n(Context Topic: {search_query})"}
            ],
            temperature=0.5,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        yield f"분석 중 오류가 발생했습니다: {e}"
