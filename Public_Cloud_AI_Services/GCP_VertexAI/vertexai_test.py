import os
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. 설정 (사용자 수정 필요)
# ---------------------------------------------------------
PROJECT_ID = "project"       # GCP 프로젝트 ID
LOCATION = "asia-northeast3"                  # 리전 (gemini 모델 지원 리전)
# 한국리전 (asia-northeast3)에서는 gemini-2.5-flash만 사용 가능
#https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/data-residency?hl=ko#asia-pacific
MODEL_ID = "gemini-2.5-flash" # 사용하려는 모델명
CREDENTIALS_FILE = "sa.json"              # 서비스 계정 키 파일명

# ---------------------------------------------------------
# 2. 인증 설정 (서비스 계정 키 파일 로드)
# ---------------------------------------------------------
if not os.path.exists(CREDENTIALS_FILE):
    print(f"Error: '{CREDENTIALS_FILE}' file not found.")
    exit(1)

# google-genai 라이브러리는 이 환경 변수를 통해 인증 정보를 자동으로 찾습니다.
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE

print(f"Authenticated using: {CREDENTIALS_FILE}")

# ---------------------------------------------------------
# 3. 클라이언트 초기화 및 호출
# ---------------------------------------------------------
try:
    # Vertex AI 클라이언트 생성
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION
    )

    # 프롬프트 정의
    prompt = "Hello! Please introduce yourself in one sentence."

    print(f"Sending prompt to {MODEL_ID}...")

    # 모델 호출 (텍스트 생성)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.7,      # 창의성 조절
            max_output_tokens=256 # 응답 길이 제한
        )
    )

    # 4. 결과 출력
    print("-" * 30)
    print("Response:")
    print(response.text)
    print("-" * 30)

except Exception as e:
    print("\n[Error Occurred]")
    print(e)