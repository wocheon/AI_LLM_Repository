import time
import configparser
from openai import OpenAI

# 설정 로드
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

# 변수 매핑
BASE_URL = config['AI_SERVER']['BaseUrl']
API_KEY = config['AI_SERVER']['ApiKey']
MODEL_NAME = config['MODEL']['Name']
SYSTEM_PROMPT = config['PROMPT']['SystemPrompt'].strip('"')
USER_QUESTION = config['TEST']['UserQuestion']

# Timings 설명 매핑
TIMINGS_DESCRIPTIONS = {
    "cache_n": "캐시 사용 횟수",
    "prompt_n": "프롬프트 토큰 수",
    "prompt_ms": "프롬프트 처리 시간(ms)",
    "prompt_per_token_ms": "프롬프트 토큰당 시간(ms)",
    "prompt_per_second": "프롬프트 처리 속도(t/s)",
    "predicted_n": "생성된 토큰 수",
    "predicted_ms": "생성 소요 시간(ms)",
    "predicted_per_token_ms": "생성 토큰당 시간(ms)",
    "predicted_per_second": "생성 속도(t/s)"
}

def extract_timings(resp):
    """응답 객체에서 timings 정보 추출"""
    try:
        # 1. 딕셔너리인 경우
        rdict = resp if isinstance(resp, dict) else resp.__dict__
        if "timings" in rdict: return rdict["timings"]

        # 2. Choices 내부에 있는 경우
        if hasattr(resp, "choices") and resp.choices:
            if hasattr(resp.choices[0], "timings"):
                return resp.choices[0].timings

        # 3. _data (숨겨진 속성)에 있는 경우
        if hasattr(resp, "_data") and isinstance(resp._data, dict):
            return resp._data.get("timings")
            
    except:
        pass
    return None

def main():
    # 1. 준비
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    print(f"질문: {USER_QUESTION}")
    print("=" * 50)
    print("답변 생성중... (Streaming=False)\n")

    # 2. 요청 (Non-streaming)
    start_time = time.time()
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_QUESTION}
            ],
            stream=False
        )
    except Exception as e:
        print(f"\n[Error] : {e}")
        return

    elapsed_time = time.time() - start_time

    # 3. 답변 출력
    answer = response.choices[0].message.content
    print(answer)
    print("\n" + "=" * 50)

    # 4. 통계(Usage) 출력
    usage = getattr(response, "usage", None)
    if usage:
        p_tokens = getattr(usage, "prompt_tokens", 0)
        c_tokens = getattr(usage, "completion_tokens", 0)
        t_tokens = getattr(usage, "total_tokens", 0)

        print(f"[ 통계 정보 ]")
        print(f"1. 소요 시간 : {elapsed_time:.2f}초")
        print(f"2. 토큰 사용량 : 입력 {p_tokens} + 출력 {c_tokens} = 합계 {t_tokens}")
        if elapsed_time > 0:
            print(f"3. 속도 : {c_tokens / elapsed_time:.2f} tokens/sec")
    else:
        print("ℹ️ Usage 정보를 받지 못했습니다.")

    # 5. Timings 출력
    timings = extract_timings(response)
    print("\n[ Timings 상세 정보 ]")
    if timings:
        for k, v in timings.items():
            desc = TIMINGS_DESCRIPTIONS.get(k, k)
            print(f" - {k:<25}: {v}  → {desc}")
    else:
        print("ℹ️ Timings 정보를 받지 못했습니다.")

if __name__ == "__main__":
    main()

