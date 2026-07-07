# **1. vLLM (High-Performance Inference Engine)**

**"엔터프라이즈 프로덕션 환경의 표준"**

## 주요 특징

*   **특징 (Characteristics)**:
    *   **PagedAttention**: 운영체제의 가상 메모리 관리 기법을 GPU KV Cache에 적용하여 메모리 낭비를 최소화하고 처리량(Throughput)을 극대화
    *   **Continuous Batching**: 요청이 들어오는 즉시 유휴 자원에 할당하여 대기 시간을 줄이는 스케줄링 기법을 사용
    *   **Tensor Parallelism**: 단일 GPU에 담기지 않는 모델을 여러 GPU에 분산 로드하여 처리.

*   **지원 모델 (Supported Models)**:
    *   **형식**: Hugging Face 표준 포맷인 **Safetensors** 또는 **PyTorch Bin**. (GGUF 미지원)
    *   **범위**: 대부분의 Transformer 기반 최신 모델(Llama 3, Qwen 2.5, Mistral, Gemma 등) 지원. AWQ, GPTQ, SqueezeLLM 등 **GPU 친화적 양자화(Quantization)** 모델 지원.

*   **동작 방식 (Operational Mechanism)**:
    *   **Memory Resident (메모리 상주)**: 실행 시 GPU 메모리(VRAM)를 **90% 이상 미리 점유**하여 런타임 할당 오버헤드 제거.
    *   **GPU Centric**: **NVIDIA CUDA**에 최적화. AMD ROCm 지원. CPU 실행(OpenVINO 등)은 PagedAttention 효율 저하로 비권장.
    *   **Server Mode**: 1회성 실행이 아닌 API 서버 데몬 형태로 상시 구동.

***

## **vLLM 설치 방법**
- **권장 환경**: Linux + NVIDIA GPU (Windows는 WSL2 필요, Docker 권장)

### **A. Linux (Native Python)**
```bash
# 1. 환경 생성 (Python 3.10 이상 권장)
conda create -n vllm python=3.10 -y && conda activate vllm

# 2. vLLM 설치
pip install vllm
```

### **B. Linux (Docker) - *Recommended***
- NVIDIA Container Toolkit 설치 필요
```bash
# Docker로 실행 시 별도 설치 없이 이미지로 바로 실행 가능합니다.
docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model Qwen/Qwen2.5-3B-Instruct
```

### **C. Windows (WSL2)**
Windows에서 vLLM을 직접 구동하는 것은 매우 복잡하므로, **WSL2(Ubuntu)**를 설치한 후 위의 **Linux (Native)** 방식을 따르는 것이 표준입니다.


***

## **모델 실행 방법**
- vLLM은 기본적으로 **OpenAI API 호환 서버**를 제공

### **1. 모델 실행 (CLI)**
```bash
# Qwen 2.5 3B Instruct 모델 다운로드 및 서버 실행
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-3B-Instruct \
    --dtype auto \
    --api-key secret-key
```

### 2. 로컬 모델 실행 (CLI)
- vLLM은 모델 폴더 경로를 직접 지정하면 인터넷(Hugging Face) 연결 없이도 로컬 파일을 로드
- 주로 `safetensors` 또는 `pytorch_model.bin` 형식을 사용

- **A. 로컬 모델 준비**
- 모델 파일들이 한 폴더에 모여 있어야 합니다.
    -  (예: `/data/models/my-local-qwen`)
*   필수 파일: `config.json`, `tokenizer.json`, `model-*.safetensors` 등

-  **B. 로컬 모델 로드 및 서버 실행**
    ```bash
    # --model 옵션 뒤에 "모델 이름" 대신 "절대 경로"를 입력합니다.
    # `--served-model-name`: API 호출 시 사용할 모델의 별칭(Alias)을 지정
    python -m vllm.entrypoints.openai.api_server \
        --model /data/models/my-local-qwen \
        --served-model-name my-custom-model \
        --tensor-parallel-size 1 \
        --port 8000
    ```

### 3. 로컬 모델 실행 (docker)
- NVIDIA Container Toolkit 설치 필요
```sh
docker run --runtime nvidia --gpus all \
    -v /home/user/models/Qwen2.5-3B-Instruct-AWQ:/models \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model /models \
    --served-model-name qwen-local \
    --dtype auto \
    --trust-remote-code
```


***


## **모델 API 호출 방법**

### 1. **API 호출 (curl - OpenAI SDK 호환)**    

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer EMPTY" \
  -d '{
    "model": "my-model",
    "messages": [
      { "role": "user", "content": "Hello!" }
    ],
    "temperature": 0.7,
    "max_tokens": 50
  }'
```


### 2. **API 호출 (Python - `requests` 사용)**

```py
import requests
import json
# 1. 설정
url = "http://localhost:8000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer EMPTY"  # vLLM은 기본적으로 키 검증 없음
}
data = {
    "model": "my-model",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain REST API briefly."}
    ],
    "temperature": 0.7
}
# 2. 요청 및 응답 처리
try:
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()  # 에러 체크
    result = response.json()
    print(result['choices'][0]['message']['content'])
except Exception as e:
    print(f"Error: {e}")
```

### 3. **API 호출 (Python - `openai` 사용)**
```python
from openai import OpenAI

# 1. 클라이언트 초기화 (vLLM 서버 주소 지정)
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY"
)

# 2. 채팅 완료 요청
completion = client.chat.completions.create(
    model="my-model",
    messages=[
        {"role": "system", "content": "You are an AI expert."},
        {"role": "user", "content": "What is vLLM?"}
    ],
    temperature=0.7,
    max_tokens=100
)

# 3. 결과 출력
print(completion.choices[0].message.content)    
```