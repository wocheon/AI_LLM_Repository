import os
from openai import OpenAI
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# ---------------------------------------------------------
# 1. 설정 (사용자 수정 필요)
# ---------------------------------------------------------
SERVICE_ACCOUNT_FILE = "sa.json"  # 키 파일 경로
PROJECT_ID = "project"    # GCP 프로젝트 ID (sa.json 안에 있어도 명시 추천)
LOCATION = "asia-northeast3"      # 리전 (서울)
MODEL_ID = "google/gemini-2.5-flash" # 모델명 (접두사 google/ 필수)

# ---------------------------------------------------------
# 2. 인증: sa.json 파일로 Access Token 생성
# ---------------------------------------------------------
# Vertex AI 사용에 필요한 스코프
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

if not os.path.exists(SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError(f"Key file '{SERVICE_ACCOUNT_FILE}' not found.")

# 서비스 계정 자격 증명 로드
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

# 토큰 갱신 (유효한 토큰 발급)
credentials.refresh(Request())
access_token = credentials.token

# ---------------------------------------------------------
# 3. OpenAI 클라이언트 초기화
# ---------------------------------------------------------
client = OpenAI(
    # Vertex AI의 OpenAI 호환 엔드포인트
    base_url=f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/openapi",
    api_key=access_token  # 여기에 Google Access Token 주입
)

# ---------------------------------------------------------
# 4. 모델 호출
# ---------------------------------------------------------
print(f"Calling {MODEL_ID} via OpenAI SDK...")

try:
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": "대한민국의 수도는 어디지?"}
        ],
        temperature=0.7,
        max_tokens=2048
    )


    # 1. 전체 응답 구조 출력 (디버깅용)
    print("Full Response Dump:")
    print(response.model_dump_json(indent=2))  # v1.x 에서는 model_dump_json() 사용

    # 2. 안전하게 content 접근
    if response.choices and response.choices[0].message.content:
        print("\nContent:", response.choices[0].message.content)
    else:
        print("\n[Warning] Content is None. Check finish_reason or safety ratings.")
        # finish_reason 확인 (예: 'content_filter'면 안전 차단됨)
        print("Finish Reason:", response.choices[0].finish_reason)

except Exception as e:
    print(f"\nError occurred: {e}")