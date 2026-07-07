# 인공지능(AI) 전체 구조와 최신 주요 분류

## 구조 요약 (트리 도식)

```txt
인공지능 (AI)
├── 머신 러닝 (Machine Learning)
|    ├── 지도 학습 (Supervised)
|    ├── 비지도 학습 (Unsupervised)
|    ├── 준지도 학습 (Semi-supervised)
|    ├── 자기 지도 학습 (Self-supervised)
|    ├── 강화 학습 (Reinforcement)
|    ├── 전이 학습 (Transfer Learning)
|    └── AutoML
├── 딥 러닝 (Deep Learning)
|    ├── 신경망 (Neural Networks)
|        ├── 합성곱 신경망 (CNN)
|        ├── 순환 신경망 (RNN)
|        ├── 그래프 신경망 (GNN)
|        └── 트랜스포머 (Transformer)
├── 대규모 언어 모델 (LLM)
|    ├── 컨텍스트 학습 (In-context Learning)
|    ├── 프로프트 엔지니어링 (Prompt Engineering)
|    └── Fine-tuning
├── 생성형 AI (Generative AI)
|    ├── 멀티모달 AI (Multimodal AI)
|    ├── 소규모 언어 모델 (SLM)
|    └── Alignment(정렬)
└── Agent AI (지능형 에이전트)
└── 연합 학습 (Federated Learning)
└── 설명가능한 AI (XAI)
```

## 인공지능 (Artificial Intelligence, AI)

- **정의**: 인간과 유사한 지능적 작업(학습, 추론, 문제 해결 등)을 컴퓨터가 수행하도록 만드는 다양한 기술과 알고리즘의 총칭

***

## AX (AI Transformation, 인공지능 전환)
- 정의: AI를 단순한 도구 수준을 넘어, 기업과 사회 운영 전반에 깊이 통합해 전면적 혁신을 이루는 과정

- 특징:
    - 기존 디지털 전환(DX)을 넘어 AI가 의사결정, 업무 실행, 비즈니스 모델 혁신에 중심적 역할 수행
    - AI가 판단, 실행, 개선까지 스스로 수행하여 지능화된 생태계 창출
    - 기업 운영, 제품·서비스 제공, 조직 문화, 고객 경험 등 모든 분야에 AI 적용 확대

- 의의: AI 기반의 차세대 혁명으로, 비즈니스 및 사회 구조를 지능형으로 재편

***

### 머신 러닝 (Machine Learning)

- **개념**: **데이터로부터 패턴을 학습**해 명시적 프로그래밍 없이 작업을 수행하는 기술
- **주요 확장 개념**:
    - **전이 학습 (Transfer Learning)**: 이미 학습된 모델의 지식을 새로운 과제에 적용해서 적은 데이터로도 우수한 성능을 달성
    - **AutoML**: 데이터 처리부터 모델 최적화까지 머신러닝 전체 과정을 자동화하는 시스템
    
#### 1. 지도 학습 (Supervised Learning)
- **정답(레이블)이** 주어진 데이터로 입력과 출력의 관계를 학습  
- **예시**: 스팸 메일 분류, 이미지 인식

#### 2. 비지도 학습 (Unsupervised Learning)
- **정답(레이블) 없이** 데이터 내 구조나 패턴을 탐색  
- **예시**: 군집화, 차원 축소

#### 3. 준지도 학습 (Semi-supervised Learning)
- **적은 양의 레이블 데이터와 많은 비레이블 데이터를 함께 활용**  
- **활용**: 라벨링 비용이 큰 환경에서 성능 개선

#### 4. 자기 지도 학습 (Self-supervised Learning)
- **데이터 내 일부 정보를 감추고 이를 예측하도록 학습**  
- **특징**: 대규모 언어/비전 모델에서 사전학습의 핵심 기법

#### 5. 강화 학습 (Reinforcement Learning)
- **에이전트**가 환경과 상호작용하며 보상을 최대화하도록 행동을 선택하는 학습 방식  
- **예시**: 게임 플레이, 자율 주행

***

### 딥 러닝 (Deep Learning)

- **정의**: 다층 신경망(Deep Neural Network)으로 복잡하고 계층적인 패턴 학습  
- **세부 구조**:
    - **신경망 (Neural Networks)**: 입력층~은닉층~출력층의 계층적 구조
        - **합성곱 신경망 (CNN)**: 이미지/영상 등 격자형 데이터 특징 추출
        - **순환 신경망 (RNN)**: 시퀀스(연속 데이터) 처리, 자연어·시계열 분석
        - **그래프 신경망 (GNN)**: 그래프 구조(노드/엣지) 데이터에서 관계와 패턴 학습
        - **트랜스포머 (Transformer)**: 대용량 데이터의 시퀀스·자연어처리(LM, LLM 등)에서 사용되는 혁신적 구조

***

### 대규모 언어 모델 및 생성형 AI

- **대규모 언어 모델 (LLM, Large Language Models)**
    - **정의**: 방대한 텍스트로 학습해 언어 이해·생성이 가능한 신경망 기반 모델
    - **예시**: GPT, BERT, ChatGPT
    - **세부 기술**:
        - **컨텍스트 학습 (In-context Learning)**: 파인튜닝 없이도 입력된 사례만 토대로 태스크 수행 가능
        - **프로프트 엔지니어링 (Prompt Engineering)**: LLM을 효과적으로 활용하기 위한 프롬프트 최적화 및 설계 기법

- **생성형 AI (Generative AI)**
    - **개념**: 텍스트, 이미지, 음성 등 다양한 콘텐츠를 생성
    - **특징**: 기존 자료를 바탕으로 새롭고 창의적인 결과물 생성  
    - **세부 분야**:
        - **멀티모달 AI (Multimodal AI)**: 텍스트·이미지·음성 등 여러 데이터 타입을 동시에 이해하고 생성
        - **소규모 언어 모델 (SLM, Small Language Models)**: 제한된 리소스 환경에 적합한 경량 LLM
    - **정렬 (Alignment)**: 생성 AI가 인간의 의도, 윤리 기준 등에 맞게 출력을 조정, 최적화하는 연구와 기술

- **Agent AI (지능형 에이전트)**
    - **정의**: 환경과 상호작용하며 목표를 달성하기 위해 스스로 판단하고 행동하는 자동화된 지능 시스템
    - **예시**: AI 비서, 업무 자동화 로봇, 게임 내 지능형 캐릭터

- **파인튜닝 (Fine-tuning)**
    - **개념**: 사전학습된 모델을 특정 과제·도메인에 맞게 추가 학습
    - **활용**: 기업 맞춤 챗봇, 의료·법률 전문 모델

***

### 기타 추천 및 최신 AI 기술

- **연합 학습 (Federated Learning)**
    - 데이터 자체는 로컬 기기(스마트폰 등)에 남기고, 모델만 중앙 서버와 공유해 학습함  
    - **특징**: 개인정보 보호, 분산 환경의 모델 학습

- **설명가능한 AI (Explainable AI, XAI)**
    - AI의 판단 근거나 과정을 이해하고 설명할 수 있도록 지원

***

## AI 모델 분류 기준

- 엔지니어링 환경(인프라) 모델의 체급을 기준으로 분류 

| 구분 (Class)     | 주요 모델 (Example)                      | 아키텍처 (Architecture)              | 프롬프트 이해 (Promptable?) | 입력 예시 (Input)                            | 출력 예시 (Output)                                     | 인프라 (Infra)            | 핵심 용도 (Use Case)                           |
| -------------- | ------------------------------------ | -------------------------------- | --------------------- | ---------------------------------------- | -------------------------------------------------- | ---------------------- | ------------------------------------------ |
| 1. NLU(이해 모델)  | BERT, Electra,RoBERTa                | Transformer Encoder Only(입력을 숫자로 압축)         | 불가능 (No)(명령어 인식 불가)   | "배터리가 너무 빨리 닳아요"(Raw Text)               | Label: 불만(Complaint)Score: 0.98                    | CPU / T4               | -  RAG 검색기 (Retriever)-  스팸/키워드 분류-  감성 분석 |
| 2. SLM(엣지 모델)  | Llama 3 8B, Phi-3,Gemma 2            | 	Transformer Decoder Only(다음 단어 예측/생성)        | 가능 (Yes)(지시 수행 가능)    | "배터리 절약 팁 3개 알려줘"(Instruction)           | "1. 화면 밝기 줄이기..."(Generated Text)                  | 노트북 / 엣지(M4, RTX 4090) | -  온디바이스 비서-  보안 문서 요약-  오프라인 번역           |
| 3. sLLM(중형 모델) | Llama 3 70B, Qwen 72B,Mixtral 8x7B   | 	Transformer Decoder Only                     | 가능 (Yes)              | "첨부된 매뉴얼 기반으로 답해"(Instruction + Context) | "매뉴얼 12페이지에 따르면..."(Grounded Text)                 | A100/H100(단일 서버)       | -  사내 전문 챗봇-  법률/의료 분석-  RAG 답변 생성         |
| 4. LLM(거대 모델)  | GPT-4, Claude 3,DeepSeek V3          | 	Transformer Decoder Only                     | 가능 (Yes)              | "이 코드 리팩토링하고 이유 설명해"(Complex Prompt)     | "```python def optimize()...```"(Code + Reasoning) | GPU 클러스터(Cloud API)    | -  복잡한 코딩-  논문 심층 분석-  창의적 글쓰기             |
| 5. LMM(멀티모달)   | GPT-4o, Gemini 1.5,Claude 3.5 Sonnet | Hybrid /Omni-Model(Visual/Audio Encoder) | 가능 (Yes)              | [이미지] "이거 얼마야?"(Image + Text)            | "사진 속 제품은 $20입니다."(Multi-modal)                    | 전용 AI 칩(TPU/LPU)       | -  실시간 음성 대화-  이미지 분석-  자율 에이전트            |


- Encoder vs Decoder 

| 아키텍처         | 핵심 동작 (Action)        | 비유 (Analogy)                          | 데이터 흐름                          |
| ------------ | --------------------- | ------------------------------------- | ------------------------------- |
| Encoder(압축기) | "정보를 이해하고 압축한다"       | 독해 시험: 지문을 읽고 핵심 내용이나 정답(번호)만 골라냄     | Text $\\rightarrow$ Vector/Label |
| Decoder(생성기) | "다음에 올 내용을 추측하여 생성한다" | 작문 시험: 앞 문장을 보고 뒤에 이어질 내용을 상상해서 글짓기 함 | Vector $\\rightarrow$ Text      |

<br>

***

<br>


