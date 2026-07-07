# 대규모 언어 모델 (LLM, Large Language Models)

## 개요 
- **정의**: 방대한 텍스트로 학습해 언어 이해·생성이 가능한 신경망 기반 모델
- **예시**: GPT, ChatGPT, QWEN, Geminai
- **세부 기술**:
    - **컨텍스트 학습 (In-context Learning)**: 파인튜닝 없이도 입력된 사례만 토대로 태스크 수행 가능
    - **프로프트 엔지니어링 (Prompt Engineering)**: LLM을 효과적으로 활용하기 위한 프롬프트 최적화 및 설계 기법

## LLM 내부 동작원리 

- LLM 내부 동작을 6단계로 구분하여 정리

| 단계 (Step)          | 동작 (Action)  | 역할 (Description)                       | 입력 (Input)      | 출력 (Output)                          |
| ------------------ | ------------ | -------------------------------------- | --------------- | ------------------------------------ |
| 1단계Tokenization    | 텍스트 분해       | 문장을 모델이 이해하는 최소 단위(토큰 ID)로 쪼갠다.        | Text String"안녕" | List of Integers[3521, 102]          |
| 2단계Embedding       | 벡터 변환        | 정수 ID를 의미를 담은 고차원 숫자 배열(Vector)로 바꾼다.  | Token ID3521    | Dense Vector[0.12, -0.5, ...]        |
| 3단계Positional Enc. | 위치 주입        | 단어의 순서 정보(위치값)를 벡터에 더해준다.              | Vector          | Vector + Pos(위치 정보 포함됨)              |
| 4단계Transformer     | 문맥 추론(핵심 연산) | Self-Attention을 통해 단어 간의 관계와 문맥을 파악한다. | Context Vectors | Refined Vectors(문맥이 반영된 벡터)          |
| 5단계Prediction      | 확률 계산        | 다음에 올 가능성이 있는 모든 단어의 점수(Logits)를 매긴다.  | Final Vector    | Logits (Probability){"안녕": 90%, ...} |
| 6단계Decoding        | 선택 및 반복      | 확률에 따라 단어를 하나 골라 출력하고, 입력에 붙여 반복한다.    | Logits          | Next Token"하세요"                      |

### 상세 설명


#### **1단계: Tokenization (토큰화)**
> **"텍스트를 숫자로 된 ID 리스트로 변환"**

*   **동작:** 입력된 문장을 모델의 어휘 사전(Vocabulary)에 있는 단어 조각(Token)으로 분할
*   **예시:** `"도커가 뭐야?"` -> `["도커", "가", "뭐", "야", "?"]`
*   **결과:** `[ID: 101, ID: 2304, ID: 994, ...]`
*   **Engineering Note:** 여기서 `UNK(Unknown)` 토큰이 많이 뜨면 모델 성능이 낮아짐 -> 이 토크나이저 효율로 인해 한국어 전용 모델을 사용

#### **2단계: Embedding (임베딩)**
> **"ID를 의미를 가진 벡터(숫자 배열)로 변환"**

*   **동작:** 각 ID(정수)를 4096차원(Llama-3 기준)의 실수 벡터로 매핑
*   **예시:** `ID: 2304` -> `[0.01, -0.54, 0.33, ...]` (4096개의 숫자)
*   **의미:** 이 숫자들에 '도커'라는 단어의 의미(컨테이너, 가상화 등)가 압축되어 있는 형태

#### **3단계: Positional Encoding (위치 인코딩)**
> **"벡터에 순서(위치) 정보를 주입"**

*   **동작:** 임베딩된 벡터에 **"나는 첫 번째 단어야", "나는 두 번째야"**라는 위치 정보를 담은 벡터를 추가 (Add).
*   **이유:** `Transformer`는 병렬 처리 구조라 순서 알수 없음. "도커가 나를 만들었다"와 "내가 도커를 만들었다"를 구분하려면 이 단계가 필수적임
*   **최신 기술:** 최신 모델(Llama 3, Phi-3)은 단순 덧셈 대신 **RoPE(Rotary Positional Embeddings)**라는 회전 변환 방식을 써서 긴 문맥도 잘 기억할수 있음

#### **4단계: Transformer Block & Attention (핵심 추론)**
> **"문맥(Context)을 파악하고 단어 간의 관계 계산"**

*   **동작:** **Self-Attention(자기 주의)** 메커니즘이 동작
*   **과정:** "도커"라는 단어가 입력되었을 때, 문장 내의 다른 단어들과의 연관성을 계산
*   **결과:** 문맥에 따라 단어 벡터의 값이 정교하게 수정. (단순한 '단어'가 아니라 '문맥 속의 의미'로 진화)

#### **5단계: Prediction (예측)**
> **"다음에 올 단어의 확률 분포 계산"**

*   **동작:** Transformer를 통과한 최종 벡터를 **Linear Layer(선형 계층)**에 통과시켜, 사전에 있는 5만~12만 개 모든 토큰에 대한 점수(Logits)를 책정.
*   **예시 출력:**
    *   `"컨테이너"`: 45%
    *   `"가상화"`: 30%
    *   `"리눅스"`: 10%
    *   `"바나나"`: 0.0001%

#### **6단계: Loop & Decoding (생성 루프)**
> **"주사위를 굴려 단어를 선택하고 다시 입력으로 넣기"**

*   **Decoding Strategy:** 확률이 제일 높은 "컨테이너"를 선택할지(Greedy), 아니면 약간의 창의성을 발휘해 "가상화"를 선택할지(Temperature, Top-P) 결정.
*   **Loop (무한 반복):**
    1.  선택된 단어: `"컨테이너"`
    2.  새로운 입력: `"도커가 뭐야? 컨테이너"`
    3.  **다시 1단계~5단계 반복**
    4.  이 과정을 `[EOS]`(문장 끝) 토큰이 나올 때까지 수십 번 반복.

### **정리: 엔지니어가 봐야 할 포인트**

1.  **1~3단계(입력 처리):** 매우 빠르게 동작하며 비용이 거의 발생하지않음
2.  **4단계(Attention):**  문장이 길어지면 해당단계에서 메모리 OOM 발생으로 병목 발생
3.  **6단계(Loop):** 한 번에 한 글자밖에 못 쓰기 때문에, 긴 답변을 요구하면 이 무거운 루프를 수백 번 돌려야함. LLM 응답이 느린 직접적인 원인.


<br>

***

<br>


# LLM 모델 포맷

### **주요 모델 포맷 및 SW 매핑 차트**

- Huggingface 등에서 LLM 모델을 받아서 사용하는 경우, 다음 포맷에 따라 용도를 구분하여 사용 가능

| 포맷 이름 (확장자/태그) | **주 용도 및 특징** | **추천 실행 SW** | **하드웨어** | **비고 (엔지니어 팁)** |
| :--- | :--- | :--- | :--- | :--- |
| **GGUF**<br>`*.gguf` | **로컬/개인용 표준**<br>CPU/Mac 최적화, 단일 파일이라 관리가 매우 편함. | **Ollama**<br>**LM Studio**<br>llama.cpp | **Apple Silicon**<br>저사양 GPU<br>CPU Only | 허깅페이스에서 다운받을 때 파일명에 `Q4_K_M`, `Q5_K_M` 붙은 걸 받으세요. (가성비 최고) |
| **AWQ**<br>`*-awq` | **GPU 추론 표준**<br>압축률 좋고 GPU 연산 속도가 매우 빠름. | **vLLM**<br>Text-Gen-WebUI<br>HuggingFace | **NVIDIA GPU** | vLLM 서버 돌릴 때 가장 권장합니다. GPTQ보다 빠르고 설정이 쉽습니다. |
| **GPTQ**<br>`*-gptq` | **구형 GPU 표준**<br>AWQ 이전에 많이 쓰임. 여전히 호환성은 가장 넓음. | **vLLM**<br>Text-Gen-WebUI<br>AutoGPTQ | **NVIDIA GPU** | 최신 모델은 AWQ로 넘어가는 추세지만, 아직 많은 구형 모델이 GPTQ로 배포됩니다. |
| **Safetensors**<br>`*.safetensors` | **원본(Unquantized)**<br>보안성이 높고 로딩 속도가 빠른 **사실상의 표준 원본 포맷**. | **vLLM**<br>HuggingFace<br>모든 파이썬 코드 | **고성능 GPU**<br>(VRAM 24GB+) | `pytorch_model.bin`의 대체재입니다. 피클(pickle) 해킹 위험이 없어 안전합니다. |
| **PyTorch Bin**<br>`*.bin` | **구형 원본**<br>예전 방식. 보안 문제(Pickle)로 Safetensors로 대체되는 중. | **vLLM**<br>PyTorch<br>Transformers | **고성능 GPU** | 요즘 나오는 모델은 대부분 Safetensors로 배포되므로 굳이 찾아서 쓸 필요 없습니다. |
| **ONNX**<br>`*.onnx` | **호환성/배포용**<br>서로 다른 프레임워크 간 변환용이나 경량화 배포용. | ONNX Runtime<br>Triton Server | CPU / GPU<br>NPU | 주로 모바일 앱이나 웹 브라우저(WebAssembly)에서 AI 돌릴 때 씁니다. |

***

### **🚀 AI 모델 서빙 & 학습 시나리오별 가이드 (The Definitive Guide)**

#### **Situation A: "회사 서버에 올려서 고성능 서비스 제공" (Production Serving)**
> **핵심 목표**: 대규모 동시 접속 처리(Concurrency), 짧은 응답 지연(Latency), GPU 효율 극대화

*   **추천 모델 포맷**: **AWQ** (권장) 또는 **GPTQ**
    *   *검색 키워드*: `Llama-3-8B-Instruct-AWQ`
*   **실행 SW**: **vLLM** (압도적 1순위)
    *   *대안*: TensorRT-LLM (엔비디아 찐 최적화가 필요할 때)
*   **추천 OS**: **Linux (Ubuntu 22.04 LTS)**
    *   Windows는 프로덕션 서버로 절대 비추천 (GPU 드라이버 오버헤드 및 스케줄링 비효율)
*   **실행 방식**: **Docker Container**
    *   *Why?* vLLM과 CUDA 버전의 의존성이 매우 민감하므로, 호스트를 더럽히지 않고 공식 이미지를 쓰는 것이 좋음.
*   **권장 하드웨어**: NVIDIA Data Center GPU (A100, H100, L4) 또는 High-end Consumer GPU (RTX 4090)

#### **Situation B: "내 맥북이나 집 PC에서 혼자 갖고 놀 거야" (Local Playground)**
> **핵심 목표**: 간편한 설치, 저전력, RAM 용량 내 실행, 직관적인 UI

*   **추천 모델 포맷**: **GGUF**
    *   *검색 키워드*: `Llama-3-8B-Instruct-GGUF` (파일: `Q4_K_M.gguf` 추천)
*   **실행 SW**:
    *   **개발자라면**: **Ollama** (터미널/API 접근 용이)
    *   **비개발자라면**: **LM Studio** (채팅 UI 제공)
*   **추천 OS**: **Mac (macOS)** 또는 **Windows 11**
    *   Mac은 Apple Silicon(M1/M2/M3)의 통합 메모리 덕분에 AI 구동에 최적.
*   **실행 방식**: **Native App (설치형 프로그램)**
    *   *Why?* 개인 PC에서는 Docker의 오버헤드나 포트 포워딩 설정또한 복잡하므로, 그냥 `.exe`나 `.dmg`로 설치해서 클릭 한 번으로 실행하는게 나음.

#### **Situation C: "모델 연구/파인튜닝(Fine-tuning)을 할 거야" (Research & Training)**
> **핵심 목표**: 모델 가중치 수정 가능성, 학습 라이브러리 호환성, 실험 재현성

*   **추천 모델 포맷**: **Safetensors** (원본 FP16/BF16)
    *   *검색 키워드*: `Llama-3-8B-Instruct` (뒤에 아무것도 안 붙은 것)
    *   *주의*: QLoRA를 쓰더라도 원본을 받아서 로드 시점에 4bit로 변환(On-the-fly quantization)하는 것이 정석.
        - 양자화 모델은 미세한 변화를 기록할 공간이 없으므로 기울기 소실 혹은 폭발로 인해 모델이 멍청해짐
*   **실행 SW**: **PyTorch** + **Hugging Face Transformers** (+ PEFT/BitsAndBytes)
    *   *프레임워크*: **Unsloth** (학습 속도 2배 빠르고 메모리 절약됨, 강력 추천), Axolotl
*   **추천 OS**: **Linux (Ubuntu)** 또는 **Windows (WSL2)**
    *   학습용 라이브러리(DeepSpeed, BitsAndBytes)는 윈도우 네이티브에서 설치가 매우 복잡. 
        - 윈도우라면 가급적 **WSL2** 사용.
*   **실행 방식**: **Python Virtual Environment (Conda/Venv)**
    *   *Why?* 학습은 실험마다 라이브러리 버전(PyTorch Nightly 등)을 자주 변경 필요. Docker는 이미지를 계속 다시 빌드해야 해서 관리 복잡도 증가.

***

### **[요약 매트릭스]**

| 시나리오 | 모델 포맷 | 실행 SW | 추천 OS | 실행 방식 |
| :--- | :--- | :--- | :--- | :--- |
| **서비스 배포** | **AWQ** | **vLLM** | **Linux** | **Docker** (필수) |
| **로컬/개인용** | **GGUF** | **Ollama** / LM Studio | **Mac / Win** | **Native App** |
| **학습/연구** | **Safetensors** | **PyTorch** (Unsloth) | **Linux** / WSL2 | **Conda** (가상환경) |	

