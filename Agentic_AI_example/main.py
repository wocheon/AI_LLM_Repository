# main.py
import logging
import traceback
import sys
import readline
from core.llm_client import get_client
from core import history, vector_cache
from config import * # --- 전체 설정 불러오기 ---
from modules import search, review, db, chat

logger = logging.getLogger() 

def setup_logging():
    """config.py 설정에 따라 로거 초기화"""
    root_logger = logging.getLogger()
    
    # 로그 레벨 설정 (문자열 -> 상수 변환)
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(level)
    
    # 기존 핸들러 제거 (중복 방지)
    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # 1. 파일 로깅 (옵션)
    if LOG_TO_FILE:
        file_handler = logging.FileHandler(LOG_FILE_NAME, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # 2. 콘솔 로깅 (옵션)
    if LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

# 실행 전 로깅 설정 적용
setup_logging()

client = get_client()
chat_history = history.ConversationHistory(max_turns=5)

# [Vector Cache] threshold 0.25 (의미적 유사도 기준)
v_cache = vector_cache.VectorCache(threshold=0.25) 

def classify_intent(user_input):
    """
    [Router] LLM 기반 의도 분류 (Semantic Routing)
    """
    # 0. [강제 모드]
    if user_input.startswith("[DB]"): return "DB"
    if user_input.startswith("[SEARCH]"): return "SEARCH"
    if user_input.startswith("[REVIEW]"): return "REVIEW"
    if user_input.startswith("[CHAT]"): return "CHAT"

    # 1. [LLM 라우팅]
    system_prompt = """
    Classify the user's input into ONE of these categories: DB, REVIEW, SEARCH, CHAT.
    
    [Definitions]
    - DB: Internal store stock, price, availability (e.g. "재고 있어?", "얼마야?")
    - REVIEW: Opinions, comparisons, pros/cons (e.g. "평가 어때?", "비교해줘", "특징")
    - SEARCH: Factual info, specs, release dates (e.g. "출시일 언제?", "스펙")
    - CHAT: Casual talk (e.g. "안녕", "고마워")
    
    [Examples]
    Input: "버즈 재고 있어?" -> Output: DB
    Input: "지난달에 몇 개 팔렸어?" -> Output: DB  <-- [추가]
    Input: "매출 알려줘" -> Output: DB           <-- [추가]    
    Input: "아이폰 가격 얼마?" -> Output: DB
    Input: "S24 평가 어때?" -> Output: REVIEW
    Input: "버즈2랑 3 비교해줘" -> Output: REVIEW
    Input: "특징 알려줘" -> Output: REVIEW
    Input: "출시일 언제야?" -> Output: SEARCH
    Input: "안녕" -> Output: CHAT
    
    [Task]
    Input: "{}" -> Output: 
    """.format(user_input)

    try:
        response = client.chat.completions.create(
            model=FAST_MODEL_NAME,
            messages=[{"role": "user", "content": system_prompt}],
            temperature=0,
            max_tokens=5
        )
        
        raw_intent = response.choices[0].message.content.strip()
        
        # [디버깅 로그]
        logger.info(f"Router Raw Output: {raw_intent}")
        
        intent = raw_intent.upper().replace(".", "").replace("OUTPUT:", "").strip().split()[0]
        
        valid_intents = ["DB", "REVIEW", "SEARCH", "CHAT"]
        if intent in valid_intents: return intent
        for v in valid_intents:
            if v in intent: return v
                
        return "CHAT"
        
    except Exception as e:
        logger.error(f"Router Error: {e}")
        return "CHAT"

def run():
    print("🛒 Context-Aware AI Agent (Intent-aware Cache) - 종료: quit")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\n질문 > ").strip()
            if not user_input: continue
            if user_input.lower() in ['quit', 'exit']: break
            if user_input.lower() == 'clear':
                chat_history.clear()
                v_cache.clear() # [추가] 캐시도 같이 날림
                print("🧹 초기화됨")
                continue

            # =================================================
            # 1. [순서 변경] 의도 파악을 가장 먼저 수행!
            # =================================================
            intent = classify_intent(user_input)
            print(f"🤔 [{intent}]", end=" ", flush=True)
            
            # 태그 제거
            clean_input = user_input
            for tag in ["[DB]", "[SEARCH]", "[REVIEW]", "[CHAT]"]:
                clean_input = clean_input.replace(tag, "").strip()

            # =================================================
            # 2. [캐시 확인] 의도(Intent) 필터링 적용
            # =================================================
            cached_ans, dist = v_cache.get(user_input, intent=intent)
            
            if cached_ans:
                print(f"⚡ [CACHE HIT] (Intent: {intent}, Dist: {dist:.4f})")
                print("AI: ", end="", flush=True)
                print(cached_ans)
                print("-" * 60)
                
                # 히스토리 업데이트
                chat_history.add_user(user_input)
                chat_history.add_ai(cached_ans)
                continue 

            print("AI: ", end="", flush=True)
            
            # 3. 실행
            response_generator = None
            context = chat_history.get_messages()

            if "DB" in intent:
                response_generator = db.run_db_agent(clean_input) 
            elif "SEARCH" in intent:
                response_generator = search.run_search(clean_input, context_messages=context)
            elif "REVIEW" in intent:
                response_generator = review.run_review(clean_input, context_messages=context)
            else:
                response_generator = chat.simple_chat(clean_input, context_messages=context)

            # 4. 스트리밍 출력 및 수집
            full_response = ""
            if response_generator:
                for token in response_generator:
                    print(token, end="", flush=True)
                    full_response += token
                print()
            
            # 대화 기록 저장
            chat_history.add_user(user_input)
            chat_history.add_ai(full_response)
            
            # =================================================
            # 5. [캐시 저장] 의도(Intent) 포함하여 저장
            # =================================================
            if full_response and "오류" not in full_response and "실패" not in full_response:
                v_cache.set(user_input, full_response, intent=intent)
            
            print("-" * 60)

        except KeyboardInterrupt:
            break
        except Exception as e:
            traceback.print_exc()

if __name__ == "__main__":
    run()
