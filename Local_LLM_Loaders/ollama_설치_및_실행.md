# **Ollama (Local Development Standard)**

**"LLM을 위한 Docker Daemon"**


## 주요 특징

*   **특징 (Characteristics)**:
    *   **Modelfile**: Dockerfile처럼 모델, 파라미터, 시스템 프롬프트를 파일로 정의해 버전 관리.
    *   **Client-Server**: 백그라운드 데몬(`ollama serve`)이 실행되며, CLI나 API로 요청 처리.
    *   **Dynamic Loading**: 요청 시 모델 로드, 일정 시간(기본 5분) 미사용 시 언로드.

*   **지원 모델 (Supported Models)**:
    *   **형식**: `GGUF` 포맷.
    *   **범위**: Ollama Registry 모델은 `pull`로 가져오며, Hugging Face GGUF 모델도 Modelfile로 Import 가능.

*   **동작 방식 (Operational Mechanism)**:
    *   **On-Demand Memory**: 요청 시 RAM/VRAM에 로드되며, `keep_alive`로 상주 시간 조절.
    *   **Hybrid Compute**: GPU VRAM에 맞춰 레이어 자동 분배. VRAM 부족 시 CPU RAM 사용 (속도 저하, OOM 방지).
    *   **Cross-Platform**: Apple Silicon, NVIDIA, AMD, CPU(AVX2) 등 하드웨어 자동 감지 및 최적화.

***


## Ollama 설치 방법
- **권장 환경**: Mac, Linux, Windows 모두 네이티브 지원

### **Linux (Native)**
```bash
# 원클릭 설치 스크립트
curl -fsSL https://ollama.com/install.sh | sh
```

### **Linux (Docker)**
```bash
# CPU 모드
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# GPU 모드 (NVIDIA Container Toolkit 필요)
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

### **Windows**
[Ollama 공식 홈페이지](https://ollama.com/download/windows)에서 `.exe` 설치 파일을 다운로드하여 실행하면 트레이 아이콘 형태로 백그라운드에서 실행됩니다.

***

## **모델 실행**
Ollama는 모델을 `pull` 명령어로 받아두면 API가 자동으로 활성화됩니다.

### **1. 모델 실행 (CLI)**
    ```bash
    # Qwen 2.5 3B 모델 다운로드 및 실행
    ollama run qwen2.5:3b
    ```
    *(참고: 사용자가 언급한 `qwen3:4b`가 출시되면 `ollama run qwen3:4b`로 변경)*

### 2.로컬 모델 실행 (CLI)

-  Ollama는 `GGUF` 파일만 인식
    - 로컬 GGUF 파일을 사용하려면 `Modelfile`을 작성하여 Ollama 내부 레지스트리에 등록`(Build)`필요

#### **A. 로컬 모델 준비**
- `.gguf` 파일 필요 (예: `/home/user/downloads/qwen2.5-3b.Q4_K_M.gguf`)
    - huggingface 등에서 gguf 형식의 모델 다운로드 가능

#### **B. Modelfile 작성 및 모델 생성 (Create)**
1.  작업 폴더에 `Modelfile`이라는 이름의 텍스트 파일을 생성합니다.
    ```dockerfile
    # Modelfile 내용
    FROM /home/user/downloads/qwen2.5-3b.Q4_K_M.gguf
    # (선택) 기본 파라미터 설정
    PARAMETER temperature 0.7
    SYSTEM "You are a smart AI assistant."
    ```
2.  터미널에서 Ollama 모델 생성 명령어를 실행합니다.
    ```bash
    ollama create my-local-qwen -f Modelfile
    ```
3.  생성된 모델 확인:
    ```bash
    ollama list
    # my-local-qwen 모델이 목록에 보이면 성공
    ```

***

## **모델 API 호출 방법**

### 1. **API 호출 (curl - Ollama 네이티브 API)**    
```sh
curl http://localhost:11434/api/chat \
  -d '{
    "model": "my-local-qwen",
    "messages": [
      { "role": "user", "content": "Why is the sky blue?" }
    ],
    "stream": false
  }'
```

### 2. **API 호출 (curl - OpenAI SDK 호환)**    
```sh
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ollama" \
  -d '{
    "model": "my-local-qwen",
    "messages": [
      { "role": "user", "content": "Why is the sky blue?" }
    ],
    "stream": false
  }'
```

### 3. **API 호출 (Python - `requests` 사용)**
```python
import requests
import json
url = "http://localhost:11434/api/generate"

payload = {
    "model": "qwen2.5:3b",
    "prompt": "Explain Docker containers briefly.",
    "stream": False
}
response = requests.post(url, json=payload)
print(response.json()['response'])
```

### 4. **API 호출 (Python - `openai` 사용)**
```python
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:11434/v1",  # Ollama 기본 포트
    api_key="ollama"  # Ollama는 API Key로 'ollama'를 관례적으로 사용
)
response = client.chat.completions.create(
    model="my-local-qwen",  # ollama create로 만든 이름
    messages=[
        {"role": "user", "content": "Why is the sky blue?"}
    ]
)
print(response.choices[0].message.content)
```
