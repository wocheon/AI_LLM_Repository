import boto3
import json
import os
from botocore.exceptions import ClientError

# 1. aws_credentials 파일 로드 (환경 변수로 설정)
def load_credentials_to_env(file_path="aws_credentials"):
    if not os.path.exists(file_path):
        print(f"ERROR: Credentials file '{file_path}' not found.")
        exit(1)

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"\'')

# 자격 증명 로드 실행
load_credentials_to_env("aws_credentials")

try:
    # 2. Bedrock Runtime 클라이언트 생성 (환경 변수 자동 사용)
    # 주의: Nova Lite On-demand는 보통 us-east-1, us-west-2 등에서 지원되므로
    # Inference Profile(us.amazon.nova-lite-v1:0)을 쓰더라도 클라이언트 리전은 해당 Profile이 활성화된 리전이어야 함.
    # ap-northeast-2(서울)에서 Cross-region 호출이 가능하다면 그대로 유지.
    client = boto3.client("bedrock-runtime", region_name="ap-northeast-2") # 안전하게 us-east-1 추천

    # 3. Model ID: On-demand 호출을 위한 Inference Profile ID 사용
    # Base model ID (amazon.nova-lite-v1:0) 대신 사용해야 함
    model_id = "apac.amazon.nova-lite-v1:0"    

    # 4. Prompt 준비
    prompt = "대한민국의 수도는 어디야?"

    # 5. Nova 모델 전용 요청 페이로드 (messages API 구조)
    native_request = {
        "schemaVersion": "messages-v1",
        "messages": [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 512,
            "temperature": 0.5,
            "topP": 0.9
        }
    }

    # JSON 변환
    request = json.dumps(native_request)

    print(f"Invoking model: {model_id}...")

    # 6. 모델 호출
    response = client.invoke_model(modelId=model_id, body=request)

    # 7. 응답 디코딩 및 파싱 (Nova 구조)
    model_response = json.loads(response["body"].read())

    # Nova 응답 경로: output -> message -> content -> [0] -> text
    response_text = model_response["output"]["message"]["content"][0]["text"]

    print("-" * 30)
    print("Response:")
    print(response_text)
    print("-" * 30)

except (ClientError, Exception) as e:
    print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
    exit(1)