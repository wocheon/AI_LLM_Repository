# **LM Studio (GUI Playground)**

**"가장 직관적인 LLM 실험실"**

## 주요 특징

*   **특징 (Characteristics)**:
    *   **Visual Configuration**: 컨텍스트 길이(Context Window), GPU Offload 비율, 프롬프트 템플릿 등을 UI 슬라이더로 조절합니다.
    *   **Hugging Face Search Integration**: 앱 내에서 Hugging Face의 GGUF 모델을 검색하고 즉시 다운로드하여 테스트할 수 있습니다.
    *   **No Dependency**: Python이나 Docker 등 별도 런타임 설치 없이 독립 실행 파일 하나로 동작합니다.

*   **지원 모델 (Supported Models)**:
    *   **형식**: **GGUF** 전용.
    *   **범위**: Hugging Face에 올라온 모든 GGUF 변환 모델을 지원합니다. (가장 범용성이 높음)

*   **동작 방식 (Operational Mechanism)**:
    *   **Manual Control (수동 제어)**: 사용자가 **"GPU Offload"** 슬라이더를 통해 몇 개의 레이어를 GPU에 올릴지 직접 결정합니다.
    *   **Single Session**: 기본적으로 한 번에 하나의 모델만 로드하여 대화합니다. (멀티 모델 동시 서빙에는 부적합)
    *   **Local Server**: 버튼 클릭 한 번으로 `localhost` API 서버를 열 수 있지만, 대규모 트래픽 처리용은 아닙니다.

***


## LM Studio 설치 방법
- **권장 환경**: Windows, Mac (Linux는 AppImage 제공)

### **A. Linux**
공식 홈페이지에서 `.AppImage` 파일을 다운로드한 후 실행 권한을 주고 실행합니다.
```bash
chmod +x LM-Studio-*.AppImage
./LM-Studio-*.AppImage
```

### **B. Windows**
[LM Studio 공식 홈페이지](https://lmstudio.ai/)에서 설치 파일을 받아 설치합니다. Docker나 별도 설정이 필요 없습니다.


## 모델 실행 방법
- LM Studio는 GUI에서 로컬 서버를 켜는 방식
- `lms` 명령을 통해 CLI를 사용가능

### **1. 모델 실행 (GUI)**
  *   좌측 돋보기 아이콘 클릭 -> `Qwen 2.5 3B` 검색.
  *   `Q4_K_M` (추천 양자화 버전) 다운로드.
  *   우측 메뉴에서 다운로드한 모델 로드.
  *   **좌측 메뉴 중 `<->` (Local Server) 아이콘 클릭 -> [Start Server] 버튼 클릭.**


### **2. 로컬 모델 실행 (GUI)**
- LM Studio는 특정 폴더를 "모델 스캔 경로"로 지정하면, 그 안의 GGUF 파일들을 자동으로 인식

-  **A. 로컬 모델 준비**
    *   모델 파일: `.gguf` 파일
    *   위치: 원하는 폴더 (예: `C:\LLM_Models` 또는 `/Users/me/Models`)

-  **B. 로컬 모델 로드 (GUI 조작)**
    1.  **LM Studio 실행** -> 좌측 **폴더 아이콘 (My Models)** 클릭.
    2.  상단에 "Models Directory" 경로가 보입니다. 여기에 위에서 준비한 폴더(`C:\LLM_Models`)를 추가하거나 해당 폴더에 파일을 넣습니다.
    3.  목록에 모델이 뜨면 **Load** 버튼을 눌러 메모리에 올립니다.
    4.  좌측 메뉴의 **Server(양방향 화살표 아이콘)** 탭으로 이동 -> **[Start Server]** 클릭.


### **3. 모델 실행 (CLI)**

- **1. `lms` CLI 설치 및 설정 (Bootstrap)**
    - A. Mac / Linux
        - `lms` 명령어를 부트스트랩
        ```bash
        # LM Studio가 설치된 상태에서 실행
        ~/.cache/lm-studio/bin/lms bootstrap
        ```
    - **B. Windows (PowerShell)**
        - CMD나 PowerShell에서 `lms bootstrap`를 통해 환경 변수 Path에 추가
        ```powershell
        # 사용자 계정 폴더 내 위치 확인
        C:\Users\%USERNAME%\.cache\lm-studio\bin\lms.exe bootstrap
        ```
-  **2. 모델 검색 (Search)**
    - 터미널에서 바로 Hugging Face의 GGUF 모델을 검색할 수 있습니다.
        ```bash
        lms search "qwen 2.5 3b"
        ```
- **3. 모델 다운로드 (Download)**
    - 원하는 모델을 선택하여 다운로드 (양자화 옵션 지정 가능)
    ```bash
    # 가장 인기 있는 양자화 버전(보통 Q4_K_M) 자동 선택
    lms get lmstudio-community/Qwen2.5-3B-Instruct-GGUF

    # 특정 파일 지정 다운로드 (예: Q4_K_M)
    lms get lmstudio-community/Qwen2.5-3B-Instruct-GGUF --file "Q4_K_M"
    ```

- **4. 로컬 서버 실행 (Server Start)**
    - 모델을 로드하고 API 서버를 띄웁니다.

    ```bash
    # 기본 포트(1234)로 서버 시작 및 모델 로드
    lms server start --model lmstudio-community/Qwen2.5-3B-Instruct-GGUF
    ```
    *   **주요 옵션**:
        *   `--port 8080`: 포트 변경
        *   `--cors=true`: CORS 허용 (웹앱 연동 시 필수)
        *   `--gpu=max`: GPU 오프로딩 최대화 (기본값은 자동 감지이나, 명시하는 것이 좋음)
        *   `--context-length 4096`: 컨텍스트 윈도우 크기 설정

- **5. 모델 언로드 및 서버 종료**
    - 더이상 실행하지 않는 모델이 있거나 서버 종료 필요 시
    ```bash
    # 실행 중인 모델 내리기
    lms unload

    # 서버 완전히 종료
    lms server stop
    ```

### **4. 로컬 모델 실행 (CLI)**
- **A. `lms load`로 직접 경로 지정 (가장 간편)**
    - gguf 파일을 사용하여 즉시 로드
    ```bash
    # 사용법: lms load <GGUF_파일_절대_경로>
    lms load /Users/myuser/Downloads/my-custom-model.gguf
    ```

- **B. lms import` 후 실행 (정석적인 관리)**
    - 모델을 LM Studio의 전용 관리 폴더(`~/.cache/lm-studio/models`)로 이동
    후 import하여 사용 
        -  `--copy` 옵션이 없으면 기본적으로 파일을 **이동(Move)**
        -  임포트가 성공하면 해당 모델의 **식별자(Model Key)**가 출력 (예: `user/my-model`)

    ```bash
    # 파일을 LM Studio 모델 저장소로 이동(Move) 또는 복사(Copy)
    lms import /path/to/my-model.gguf --copy

    # 임포트된 모델 로드
    lms load user/my-model
    ```

***


## **모델 API 호출 방법**
- LM Studio도 OpenAI API 형식에 따라 호출

### 1. **API 호출 (curl - OpenAI SDK 호환)**    
```sh
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local-model",
    "messages": [
      { "role": "user", "content": "Hello!" }
    ],
    "temperature": 0.7
  }'
```


###  2. **API 호출 (Python - OpenAI SDK 호환)**
```python
# LM Studio는 기본적으로 포트 1234를 사용합니다.
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
)
completion = client.chat.completions.create(
    model="local-model", # LM Studio는 현재 로드된 모델을 사용하므로 이름이 중요하지 않음
    messages=[
        {"role": "system", "content": "Always answer in Korean."},
        {"role": "user", "content": "What is CI/CD?"}
    ],
    temperature=0.7,
)
print(completion.choices[0].message.content)
```

### 3. **API 호출 (Python - `requests` 사용)**

 ```python
 import requests
 import json
 
 # 1. LM Studio 서버 설정 (기본 포트 1234)
 url = "http://localhost:1234/v1/chat/completions"
 
 # 2. 헤더 설정 (JSON 형식)
 headers = {
     "Content-Type": "application/json",
     # LM Studio는 로컬이라 키가 필요 없지만, 포맷 유지를 위해 더미 값 삽입
     "Authorization": "Bearer lm-studio" 
 }
 
 # 3. 데이터 페이로드 설정
 data = {
     "model": "local-model", # LM Studio는 GUI에 로드된 모델을 쓰므로 이름은 무관
     "messages": [
         {"role": "system", "content": "You are a helpful coding assistant."},
         {"role": "user", "content": "Write a Python Hello World function."}
     ],
     "temperature": 0.7,
     "stream": False # 답변을 한 번에 받음
 }
 
 # 4. POST 요청 보내기
 try:
     response = requests.post(url, headers=headers, json=data)
     response.raise_for_status() # 200 OK가 아니면 예외 발생
 
     # 5. 결과 파싱
     result = response.json()
     print("Response Status:", response.status_code)
     print("Content:", result['choices'][0]['message']['content'])
 
 except requests.exceptions.RequestException as e:
     print(f"Error calling LM Studio: {e}")
 ```