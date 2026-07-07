import time
import configparser
import tiktoken
import sys
from openai import OpenAI

# 설정 로드
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

BASE_URL = config['AI_SERVER']['BaseUrl']
API_KEY = config['AI_SERVER']['ApiKey']
MODEL_NAME = config['MODEL']['Name']
SYSTEM_PROMPT = config['PROMPT'].get('SystemPrompt', "당신은 도움이 되는 어시스턴트입니다.").strip('"')

def main():
    try:
        encoder = tiktoken.get_encoding("cl100k_base")
    except:
        encoder = None
        
    # 1. OpenAI 클라이언트 초기화
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    print("=" * 50)
    print(f"🤖 AI 챗봇 ({MODEL_NAME}) - OpenAI 라이브러리 사용")
    print("   - 대화를 종료하려면 'quit' 또는 'exit'를 입력하세요.")
    print("=" * 50)

    while True:
        try:
            sys.stdout.write("\n질문(User) > ")
            sys.stdout.flush()
            user_input = sys.stdin.readline().strip()
        except KeyboardInterrupt:
            print("\n\n[강제 종료] 프로그램을 종료합니다.")
            break
            
        if not user_input:
            continue
            
        if user_input.lower() in ["quit", "exit"]:
            print("\n대화를 종료합니다.")
            break

        print("-" * 50)
        print("답변 (AI)  > ", end="", flush=True)

        start_time = time.time()
        full_response = ""

        try:
            url = f"{BASE_URL}/chat/completions"
            headers = {"Content-Type": "application/json; charset=utf-8"}

            # 2. 'openai' 라이브러리를 사용하여 스트리밍 API 요청
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                stream=True,
            )

            # 3. 스트림 응답 처리
            for chunk in stream:
                # chunk.choices[0].delta.content가 비어있지 않은 경우에만 처리
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    print(content, end="", flush=True)
            
            print() 

        except KeyboardInterrupt:
            print("\n\n[응답 중단] 다음 질문을 입력하세요.")
            continue
        except Exception as e:
            print(f"\n[API 오류] : {e}")
            continue

        elapsed = time.time() - start_time
        if encoder:
            p_tokens = len(encoder.encode(user_input))
            c_tokens = len(encoder.encode(full_response))
            tps = c_tokens / elapsed if elapsed > 0 else 0
            stats = f"입력: {p_tokens}, 출력: {c_tokens}"
        else:
            tps = 0
            stats = "토큰 정보 없음"

        print("-" * 50)
        print(f"⏱️  {elapsed:.2f}초 | {tps:.1f} 토큰/초 | {stats}")

if __name__ == "__main__":
    main()
