# AI/LLM Infrastructure Repository 작성 규칙

## 저장소의 성격

이 저장소는 처음부터 끝까지 순서대로 읽는 Guide나 교육 과정이 아니다. AI/LLM Infrastructure와 관련된 내용을 **비슷한 기술 요소끼리 모아 두는 주제별 참고 자료**로 구성한다.

- 특정 직무나 독자 Persona를 전제로 설명하지 않는다.
- 문서에 임의의 학습 순서나 성숙도 단계를 부여하지 않는다.
- 서로 독립적인 주제를 억지로 연결하지 않는다.
- 필요한 문서를 바로 열어 해당 주제만 확인할 수 있게 작성한다.

## 기본 구조

`AI_LLM_Infrastructure_Guide/` 아래에 작성 순서를 나타내는 두 자리 번호를 붙인 평면 Markdown 파일을 둔다.

```text
AI_LLM_Infrastructure_Guide/
├── README.md
├── 01_ai_models.md
├── 02_gpu_system.md
├── 03_gpu_execution_environment.md
├── 04_model_execution.md
├── 05_infrastructure_sizing.md
├── 06_public_cloud_gpu_and_maas.md
└── 07_rag_and_model_training.md
```

- `README.md`는 문서 목록과 각 파일이 포함하는 주제만 보여준다. 개요, 대상 독자, 권장 읽기 순서를 작성하지 않는다.
- 본문 파일명은 `01_주제.md`, `02_주제.md` 형식을 사용한다. 번호는 작성·정리 순서만 나타내며 선행학습 관계를 뜻하지 않는다.
- 관련 내용이 한 문서 안에서 자연스럽게 구분되면 하위 파일을 만들지 않고 Heading으로 나눈다.
- 한 문서가 지나치게 커져 독립 조회가 어려울 때만 하위 파일 또는 디렉토리 분리를 검토한다.
- 새 파일을 추가할 때는 기존 문서에 포함할 수 없는 독립 주제인지 먼저 확인한다.

## 문서 구성

각 문서는 다음 형태를 기본으로 한다.

```text
# 주제

## 1. 구성요소 A
### 1.1. 세부 요소 A-1
### 1.2. 세부 요소 A-2

## 2. 구성요소 B
### 2.1. 세부 요소 B-1

## 3. 정리 또는 확인 항목

## 4. References
```

- `README.md`를 제외한 본문 문서는 `1`, `1.1`, `1.2` 형태의 숫자 Heading을 사용한다.
- 대단락 번호는 문서 안에서 연속되어야 하며, 하위 번호는 대단락이 바뀔 때 다시 `1`부터 시작한다.
- 번호는 파일 간 순서나 선후관계를 뜻하지 않고 해당 문서 안의 단락을 구분하는 용도로만 사용한다.
- 서론은 해당 파일에서 다루는 범위를 한두 문장으로 설명하는 수준으로 제한한다.
- `Prerequisites`, `Previous`, `Next`, `Decision stage`, 역할별 Reading path를 만들지 않는다.
- 모든 문서에 동일한 배경 설명이나 공통 체크리스트를 반복하지 않는다.
- 별도의 결론이 필요하지 않으면 형식적으로 추가하지 않는다.

## 내용 배치 기준

### `01_ai_models.md`

AI 모델의 종류와 언어 관련 Workload가 인프라 자원을 어떻게 사용하는지 정리한다.

- NLP, NLU, NLG
- 전통적인 ML, CNN/RNN/LSTM, Transformer, SLM/sLLM/LLM
- Parameter, Weight, Precision, Quantization
- Token, Tokenizer, Embedding, Context
- Transformer Layer, Attention, KV Cache
- Training, Inference, Prefill, Decode, Batch
- TTFT, TPOT/ITL, Token/sec, Throughput
- Fine-tuning, RAG, Agent와 Serving Runtime의 개념 구분

### `02_gpu_system.md`

GPU 중심 시스템을 구성하는 하드웨어와 소프트웨어 요소를 정리한다.

- GPU, VRAM, Compute, Memory Bandwidth
- CPU, RAM, Storage, Network
- Multi-GPU, Interconnect, Topology
- Driver, CUDA/가속기 Runtime, Framework, Container, Serving Runtime
- GPU 공유와 격리

### `03_gpu_execution_environment.md`

GPU Host, Container와 Cluster에서 모델 실행 환경을 구성하는 방법을 정리한다.

- NVIDIA Driver, CUDA Toolkit/Runtime, cuDNN과 Framework
- Host와 Container의 GPU 실행 환경
- Kubernetes GPU Node와 Device Plugin
- Time-slicing, MPS, MIG와 vGPU
- Slurm GPU GRES, Job과 Device 격리

### `04_model_execution.md`

Model Artifact를 확보하고 Local 또는 GPU Server에서 실행·Serving하는 방법을 정리한다.

- Hugging Face Hub Download와 Hosted Inference API의 차이
- Transformers를 사용한 직접 실행
- Ollama, llama.cpp, LM Studio와 Docker Model Runner
- vLLM 기반 GPU Serving과 API 호출 테스트
- NLU·분류·Embedding Model을 위한 FastAPI Endpoint 구성과 호출 테스트
- FastAPI Worker별 Model·VRAM 중복 Loading과 Health·Readiness 확인
- 양자화 Model 실행과 Runtime 호환성

### `05_infrastructure_sizing.md`

Model Spec과 Workload 조건을 실제 Infrastructure Spec으로 변환하는 방법을 정리한다.

- Weight, KV Cache, Activation과 Training Memory 계산
- 단일 GPU 수용 여부와 Multi-GPU 산정
- CPU, RAM, Storage와 Network 산정
- 제한된 환경의 Quantization, Offload와 Context·Batch 최적화
- 실제 Benchmark를 사용한 산정값 검증

### `06_public_cloud_gpu_and_maas.md`

AWS, Microsoft Azure와 Google Cloud에서 GPU Infrastructure 및 Model API를 제공하는 방식을 정리한다.

- GPU VM, Managed Kubernetes GPU Node와 Managed AI Compute의 차이
- Cloud별 GPU Machine Family와 GPU·CPU·RAM·Network 결합 방식
- Region·Zone, Quota와 실제 Capacity 제약
- On-demand, Reservation과 Spot 사용 방식
- Amazon Bedrock, Microsoft Foundry Models와 Vertex AI MaaS
- MaaS의 Serverless·Provisioned 처리 방식, 인증, Network와 데이터 경계
- 직접 Hosting과 MaaS의 Control, Portability, Cost와 운영 책임 비교
- 변동 가능한 SKU·Model·Region 정보의 확인 날짜와 갱신 방법

### `07_rag_and_model_training.md`

RAG Pipeline을 구성·운영하고 NLU 또는 LLM을 추가 학습하는 방법을 정리한다.

- Document Parsing, Chunking, Embedding, Vector Index, Retrieval과 Reranking
- Offline Indexing과 Online Serving의 자원 및 장애 경계
- RAG API 구성, 호출 테스트, 문서·Index Version 관리와 품질 평가
- Pre-training, Continued Pre-training, SFT, PEFT, LoRA·QLoRA와 Preference Tuning
- NLU Text Classification 및 LLM Fine-tuning 실행 예제
- Single GPU, Multi-GPU와 Slurm 기반 학습
- Training Memory, Mixed Precision, Gradient Accumulation과 Checkpoint
- RAG, Fine-tuning 또는 두 방식을 함께 사용할 때의 선택 기준

## 작성 관점

- AI 알고리즘의 수학적 설명보다 CPU, RAM, GPU, VRAM, Storage, Network에 미치는 영향을 설명한다.
- 기술 정의는 단독으로 끝내지 않고 자원·성능·운영 영향과 함께 기록한다.
- 장점만 나열하지 않고 제약, 실패 형태, 비용과 운영 책임을 함께 다룬다.
- 특정 제품을 보편적인 정답처럼 표현하지 않는다.
- 비교가 필요한 경우에만 표를 사용하며, 표의 행과 열을 불필요하게 늘리지 않는다.
- Mermaid와 ASCII Diagram은 글보다 구조를 명확하게 보여줄 때만 사용한다.

## 용어와 문체

- 본문은 한국어를 기본으로 한다.
- 제품명, API, Metric처럼 원문이 필요한 용어만 영어로 쓴다.
- 같은 문단에서 한국어와 영어 표현을 불필요하게 반복하지 않는다.
- 문장은 짧고 직접적으로 작성한다.
- `항상`, `완전 관리`, `무제한`, `보장`과 같은 단정은 공식 계약이나 검증 결과가 있을 때만 사용한다.
- 독자를 설득하기 위한 수식어와 일반론을 줄이고 확인 가능한 사실을 우선한다.

## 링크 원칙

- 문서 간 순서를 만들기 위한 링크를 추가하지 않는다.
- 다른 파일에 상세 설명이 있고 현재 문맥에 실제로 필요한 경우에만 링크한다.
- 링크 없이 한두 문장으로 이해할 수 있는 내용은 현재 문서 안에서 설명한다.
- 존재하지 않는 미래 파일로 링크하지 않는다.
- 외부 링크는 가능하면 해당 주장과 직접 관련된 공식 문서를 사용한다.

## 자료 재사용

- 기존 Repository의 원본 자료는 수정, 삭제, 이동하지 않는다.
- 기존 내용을 복사하지 않고 사실과 경험을 새 주제 구조에 맞게 다시 정리한다.
- 오래된 서비스명, 모델 목록, GPU SKU, 가격, 리전 정보는 그대로 재사용하지 않는다.
- 기존 자료와 공식 문서가 충돌하면 최신 공식 문서를 기준으로 하고 변경 사실을 기록한다.
- 출처가 불분명한 내부 Scheduler, 물리 Capacity, 성능 보장 관련 주장은 단정하지 않는다.

## 최신성 및 References

- 제품 기능, 서비스명, 지원 리전, Quota, 구매 방식, 가격처럼 변동 가능한 내용은 공식 문서로 확인한다.
- 명시적인 제품 사실을 사용한 문서는 하단에 `References`를 둔다.
- 가격표, 전체 GPU SKU, 전체 모델 카탈로그를 Markdown에 복제하지 않는다.
- 확인 날짜가 의미 있는 경우 Reference 근처에 날짜를 기록한다.
- Preview, Deprecated, Retirement 상태는 본문에서 명확히 표시한다.

## 작업 규칙

- 요청받은 주제와 파일만 수정한다.
- 관련 없는 문서를 함께 정리하거나 전면 재작성하지 않는다.
- 기존 변경사항이 있으면 사용자의 작업으로 간주하고 보존한다.
- 파일 추가 전 기존 문서와 내용이 중복되는지 검색한다.
- 작업 후 Markdown Link, Heading 구조, Code fence와 변경 파일 범위를 확인한다.

## 금지하는 구성

- `00_overview`, `01_foundations`, `02_platforms` 같은 단계형 섹터
- 모든 파일을 연결하는 선행·후속 문서 체계
- 대상 독자와 권장 읽기 순서를 위한 별도 문서
- 같은 비교표와 설명을 여러 파일에 복제하는 방식
- 공급자별로 일반 개념을 반복한 별도 교과서
- 내용보다 Metadata와 체크리스트가 더 큰 문서
- 향후 작성할 문서를 미리 대량으로 만드는 빈 Skeleton
