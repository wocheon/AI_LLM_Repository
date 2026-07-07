import time
import configparser
import tiktoken
from openai import OpenAI

# 설정 파일 읽기
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

# 변수 매핑
BASE_URL = config['AI_SERVER']['BaseUrl']
API_KEY = config['AI_SERVER']['ApiKey']
MODEL_NAME = config['MODEL']['Name']
SYSTEM_PROMPT = config['PROMPT']['SystemPrompt'].strip('"')
USER_QUESTION = config['TEST']['UserQuestion']

def main():
    # 1. 준비
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    encoder = tiktoken.get_encoding("cl100k_base")

    print(f"모델명: {MODEL_NAME}")
    print(f"질문: {USER_QUESTION}")
    print("=" * 50)
    print("답변 생성중... (Streaming)\n")

    # 2. API 요청 및 스트리밍
    start_time = time.time()
    full_response = ""

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_QUESTION}
            ],
            stream=True
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_response += text
                print(text, end="", flush=True)

    except Exception as e:
        print(f"\n[Error] : {e}")
        return

    # 3. 통계 계산
    elapsed = time.time() - start_time
    prompt_tokens = len(encoder.encode(USER_QUESTION))
    completion_tokens = len(encoder.encode(full_response))
    total_tokens = prompt_tokens + completion_tokens

    # 4. 결과 출력
    print("\n\n" + "=" * 50)
    print(f"[ 통계 정보 ]")
    print(f"1. 소요 시간 : {elapsed:.2f}초")
    print(f"2. 토큰 : 입력 {prompt_tokens} + 출력 {completion_tokens} = 합계 {total_tokens}")
    if elapsed > 0:
        print(f"3. 속도 : {completion_tokens / elapsed:.2f} tokens/sec")

if __name__ == "__main__":
    main()
