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
    print("   - 컨텍스트 유지 토글: 'toggle_context'")
    print("   - 후속질문 가능 여부 자동 검사: 'check_followup'")
    print("=" * 50)

    # 메시지 히스토리 (system 메시지로 시작)
    keep_context = True  # 기본: 후속질문(컨텍스트 유지) 허용
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

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

        # 특수 명령 처리
        if user_input.strip().lower() == "toggle_context":
            keep_context = not keep_context
            mode = "유지" if keep_context else "비유지(싱글턴)"
            print(f"[설정 변경] 컨텍스트 유지 모드: {mode}")
            if not keep_context:
                # 히스토리를 시스템 프롬프트만 남겨 재시작
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            continue

        if user_input.strip().lower() == "check_followup":
            # 자동 검사: 이전 대화(히스토리)가 있는 경우, 모델에 간단히 '후속질문 가능 여부'를 물어봄
            probe = "지금까지의 대화 맥락을 유지한 상태에서 후속 질문을 받을 수 있습니까? '네' 또는 '아니오'로만 답해주세요."
            probe_messages = list(messages) if keep_context else [{"role": "system", "content": SYSTEM_PROMPT}]
            probe_messages.append({"role": "user", "content": probe})
            try:
                resp = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=probe_messages,
                    stream=False,
                )
                # 응답 추출: 다양한 SDK 응답 형태에 대응
                text = ""
                if hasattr(resp, "choices") and len(resp.choices) > 0:
                    # OpenAI-like: resp.choices[0].message.content
                    choice = resp.choices[0]
                    if hasattr(choice, "message") and choice.message:
                        text = choice.message.get("content") if isinstance(choice.message, dict) else getattr(choice.message, "content", "")
                    else:
                        text = getattr(choice, "text", "")
                text = (text or "").strip().lower()
                if "네" in text or "yes" in text or text.startswith("y"):
                    print("[검사 결과] 후속질문 가능(모델이 맥락을 유지한다고 응답함).")
                elif "아니오" in text or "no" in text or text.startswith("n"):
                    print("[검사 결과] 후속질문 불가(모델이 맥락을 유지하지 않는다고 응답함).")
                    print("→ 'toggle_context'로 컨텍스트 유지 모드를 켜거나, 컨텍스트를 수동으로 관리하세요.")
                else:
                    print(f"[검사 결과] 응답 판별 불가: '{text}'")
            except Exception as e:
                print(f"[검사 오류] {e}")
            continue

        print("-" * 50)
        print("답변 (AI)  > ", end="", flush=True)

        start_time = time.time()
        full_response = ""

        # 요청할 메시지 구성
        if keep_context:
            messages.append({"role": "user", "content": user_input})
            req_messages = messages
        else:
            # 싱글턴 모드: 시스템 + 현재 유저만 전송
            req_messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_input}]

        try:
            # 2. 'openai' 라이브러리를 사용하여 스트리밍 API 요청
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=req_messages,
                stream=True,
            )

            # 3. 스트림 응답 처리
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    print(content, end="", flush=True)
            
            print() 

            # 대화 히스토리 갱신 (keep_context 모드일 때만)
            if keep_context:
                messages.append({"role": "assistant", "content": full_response})

        except KeyboardInterrupt:
            print("\n\n[응답 중단] 다음 질문을 입력하세요.")
            # 스트리밍 중 중단 시 히스토리에서 마지막 user 항목 제거하지 않음(원하면 제거 가능)
            continue
        except Exception as e:
            print(f"\n[API 오류] : {e}")
            continue

        elapsed = time.time() - start_time
        if encoder:
            try:
                p_tokens = len(encoder.encode(user_input))
                c_tokens = len(encoder.encode(full_response))
            except:
                p_tokens = c_tokens = 0
            tps = c_tokens / elapsed if elapsed > 0 else 0
            stats = f"입력: {p_tokens}, 출력: {c_tokens}"
        else:
            tps = 0
            stats = "토큰 정보 없음"

        print("-" * 50)
        print(f"⏱️  {elapsed:.2f}초 | {tps:.1f} 토큰/초 | {stats}")

if __name__ == "__main__":
    main()