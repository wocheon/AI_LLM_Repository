# AI 모델과 언어 Workload

AI 모델은 하나의 기준으로만 나뉘지 않는다. 학습 방법, 신경망 구조, 입력과 출력, 모델 크기, 실행 목적이 서로 다른 분류 축이다. NLU, Fine-tuning, RAG, Agent, vLLM도 같은 종류의 용어가 아니므로 먼저 위치를 구분해야 한다.

## 1. AI 모델의 기본 분류

### 1.1. AI, Machine Learning, Deep Learning

```text
Artificial Intelligence
└── Machine Learning
    └── Neural Network
        └── Deep Learning
            ├── CNN
            ├── RNN / LSTM
            └── Transformer
                ├── Encoder 계열
                ├── Decoder 계열
                └── Encoder-Decoder 계열
```

- **Artificial Intelligence(AI)**는 판단, 예측, 생성, 계획처럼 지능이 필요한 작업을 컴퓨터로 수행하는 넓은 범위다.
- **Machine Learning(ML)**은 데이터에서 규칙을 학습하는 AI 구현 방식이다.
- **Neural Network**는 연결된 계산 계층의 Weight를 학습하는 ML 모델이다.
- **Deep Learning**은 여러 신경망 계층에서 특징을 학습한다. 모델이 커질수록 저장해야 할 Weight와 수행할 Tensor 연산이 증가한다.

이 계층은 포함 관계다. LLM은 AI와 별개의 기술이 아니라 Transformer 기반 Deep Learning 모델의 한 종류다.

### 1.2. LLM 이전의 모델

| 모델 계열 | 주로 처리한 문제 | 계산 특성 | 인프라 특성 |
| --- | --- | --- | --- |
| 전통적인 ML | 분류, 회귀, 군집화 | 사람이 만든 Feature와 비교적 작은 행렬 | CPU와 RAM만으로 처리 가능한 경우가 많음 |
| CNN | 이미지, 지역적 Pattern | Convolution을 대량 반복 | 학습과 대규모 추론에서 GPU 효과가 큼 |
| RNN/LSTM | 문장, 음성, 시계열 | 이전 Step 결과를 다음 Step에서 사용 | 순차 의존성 때문에 병렬화가 제한됨 |
| Word Embedding + 분류기 | 문서 분류, 검색, 유사도 | 단어 Vector와 Task별 모델 | 여러 작은 모델을 개별 배포하는 형태가 많음 |
| Encoder Transformer | 문장 이해, 분류, 추출 | 입력 Token을 병렬 처리하는 Attention | Training은 GPU가 유리하고 작은 추론은 CPU도 가능 |

LLM 이전에도 자연어 처리는 존재했다. 차이는 `언어를 이해하는가`가 아니라 각 문제마다 별도 Feature, 모델 또는 Output Head를 만드는 경우가 많았다는 점이다.

## 2. NLP, NLU, NLG

### 2.1. NLP

Natural Language Processing(NLP)은 컴퓨터가 사람의 언어를 처리하는 전체 영역이다. 입력 전처리부터 이해, 검색, 번역, 생성까지 포함한다.

```text
NLP
├── 언어 분석과 이해: NLU
├── 언어 생성: NLG
└── 공통 처리: Tokenization, Embedding, 검색, 평가 등
```

### 2.2. NLU

Natural Language Understanding(NLU)은 텍스트의 의미, 의도, 대상과 관계를 구조화된 결과로 해석하는 문제 영역이다.

대표 작업은 다음과 같다.

- 문장·문서 분류
- 의도 분류
- 감성 분석
- 개체명 인식
- 관계 추출
- 의미 유사도
- 질의응답과 자연어 추론

NLU는 특정 모델 구조나 크기를 뜻하지 않는다. Logistic Regression 같은 전통 모델, CNN/RNN, BERT 같은 Encoder Transformer, 생성형 LLM 모두 NLU 작업을 수행할 수 있다.

기존 Repository의 KoBERT·KoELECTRA·DeBERTa 감성분석은 전형적인 NLU 사례다. 텍스트를 입력받아 긍정·부정·중립 같은 Label을 출력하므로 긴 문장을 생성할 필요가 없다.

### 2.3. NLG

Natural Language Generation(NLG)은 요약, 번역, 답변, 코드처럼 새로운 Token Sequence를 생성한다. Decoder 또는 Encoder-Decoder 계열이 주로 사용된다.

NLU와 NLG는 배타적이지 않다. 대화형 LLM은 입력의 의도와 문맥을 해석하는 NLU와 응답을 생성하는 NLG를 한 요청 안에서 함께 수행한다.

### 2.4. NLU와 NLG의 인프라 차이

| 항목 | 분류·추출 중심 NLU | 생성형 NLG/LLM |
| --- | --- | --- |
| 출력 | Label, Score, 짧은 Span/Vector | 길이가 변하는 Token Sequence |
| 실행 | 입력을 한 번 처리하는 경우가 많음 | 입력 처리 후 Token을 순차 생성 |
| 상태 | 요청 중간 상태가 비교적 작음 | Context와 KV Cache가 누적됨 |
| Batch | 고정 길이 Batch 구성이 상대적으로 쉬움 | 요청별 입력·출력 길이 차이가 큼 |
| 주요 지표 | 요청 지연, 요청/초, 정확도/F1 | TTFT, Token/sec, 동시성, 완료 지연 |
| 자원 | 소형 모델은 CPU 추론도 현실적 | 큰 Weight와 KV Cache 때문에 GPU/가속기 의존도가 높음 |

따라서 `NLU 모델은 CPU`, `LLM은 GPU`처럼 고정해서는 안 된다. 모델 크기, 정밀도, Batch, SLO와 실행 Runtime을 함께 봐야 한다.

## 3. Transformer 기반 언어 모델

Transformer는 Attention을 사용해 Token 사이의 관계를 계산하는 신경망 구조다. RNN의 순차 계산을 줄여 학습 시 Token 축의 병렬 처리를 확대했고, 모델과 Dataset을 크게 확장하기 쉬워졌다.

### 3.1. Encoder 계열

Encoder는 입력 전체의 양방향 문맥을 반영한 표현을 만든다. BERT, RoBERTa, ELECTRA와 그 파생 모델이 대표적이다.

주요 용도:

- 문서·의도·감성 분류
- 개체명 인식과 정보 추출
- 문장 유사도와 Embedding
- 검색용 Retriever와 Reranker

인프라 관점에서는 입력 Token을 한 번에 처리하므로 Batch 추론에 유리하다. 모델이 작고 지연 요구가 느슨하면 CPU로도 운영할 수 있고, 높은 처리량이나 Fine-tuning에는 GPU가 유리하다.

### 3.2. Decoder 계열

Decoder 언어 모델은 앞의 Token을 바탕으로 다음 Token을 반복해서 예측한다. 현대적인 생성형 LLM의 일반적인 구조다.

```text
Prompt 입력
→ 전체 Prompt 처리(Prefill)
→ 첫 Token 생성
→ 이전 상태를 KV Cache에서 읽음
→ 다음 Token 생성(Decode)
→ 종료 조건까지 반복
```

Weight뿐 아니라 요청별 KV Cache가 VRAM을 사용한다. Context, 동시 요청과 출력 길이가 늘면 같은 GPU에서 처리할 수 있는 Batch와 사용자 수가 줄어들 수 있다.

### 3.3. Encoder-Decoder 계열

Encoder가 입력을 해석하고 Decoder가 출력을 생성한다. 번역, 요약, Text-to-text 작업에 사용된다. 입력과 출력 양쪽 계산 및 메모리를 고려해야 하지만, 실제 요구량은 모델 구조와 요청 형태에 따라 달라진다.

### 3.4. Multimodal 모델

텍스트 외에 이미지, 음성, 영상 등을 함께 처리한다. 별도의 Encoder나 Projector가 추가될 수 있으며, 입력 해상도·Frame·Audio 길이가 Token과 Activation을 증가시킨다.

멀티모달이라는 이유만으로 특정 전용 가속기가 필수인 것은 아니다. 지원 연산, 메모리, Runtime과 처리량에 맞춰 GPU, TPU, NPU 등 후보를 검증한다.

## 4. SLM, sLLM, LLM

### 4.1. 고정된 Parameter 경계는 없다

SLM(Small Language Model), sLLM, LLM은 업계에서 일관된 Parameter 기준으로 정의되지 않는다. 같은 8B 모델도 클라우드 Cluster 기준으로는 작고, 모바일 장치 기준으로는 클 수 있다. 일부 국내 자료에서 SLM과 sLLM을 서로 다른 체급으로 구분하지만 보편적인 표준은 아니다.

인프라 설계에서는 이름 대신 다음 값을 사용한다.

- Parameter 수와 Weight 정밀도
- 모델 Architecture와 Layer 수
- 최대 Context Length
- 입력·출력 Modality
- 평균·최대 입력과 출력 Token
- 동시 요청과 Batch
- Training, Fine-tuning 또는 Inference 여부

### 4.2. 크기에 따른 일반적인 변화

```text
Parameter 증가
→ Weight 파일 증가
→ Disk와 다운로드 시간 증가
→ RAM/VRAM 증가
→ 단일 GPU 수용 실패 가능
→ Multi-GPU와 고속 Interconnect 필요 가능
```

작은 모델은 낮은 비용, 짧은 지연, Edge/CPU 실행 가능성이 장점이다. 큰 모델은 더 넓은 능력을 제공할 수 있지만 품질은 Parameter 수만으로 결정되지 않는다. Dataset, 학습 방식, Architecture와 작업 적합성을 실제 평가해야 한다.

## 5. 모델을 구성하는 요소

### 5.1. Parameter와 Weight

Parameter는 학습 과정에서 조정되는 값의 개수이고, Weight는 학습이 끝난 뒤 저장된 실제 값이다. Bias와 정규화 계층 값 등 다른 학습 Parameter도 모델 파일에 포함될 수 있다.

Weight 메모리의 이론적 하한은 다음과 같이 근사할 수 있다.

```text
Weight bytes ≈ Parameter 수 × Parameter당 bit 수 ÷ 8
```

실행 시에는 Weight 외에도 Activation, KV Cache, Runtime Workspace와 메모리 단편화가 추가된다. 따라서 이 식만으로 필요한 VRAM을 확정할 수 없다.

### 5.2. Token과 Tokenizer

Tokenizer는 문자열을 모델 Vocabulary의 Token ID로 변환하고, 출력 Token ID를 다시 문자열로 변환한다. Token은 반드시 한 단어나 한 글자와 같지 않다.

Tokenizer가 달라지면 같은 문장의 Token 수, 최대 Context 내 수용량, 처리 시간과 API 비용이 달라진다. Weight만 교체하고 다른 Tokenizer를 사용하면 입력 의미와 출력 복원이 손상될 수 있다.

### 5.3. Embedding

Embedding은 Token이나 문장을 고차원 Vector로 표현한다.

- 언어 모델 내부의 Token Embedding은 Token ID를 Transformer가 처리할 Tensor로 바꾼다.
- 검색용 Embedding 모델은 문서와 질의를 비교할 Vector를 출력한다.

둘 다 `Embedding`이라고 부르지만 수명주기와 실행 경로가 다르다. 검색용 Embedding을 별도 서비스로 운영하면 모델 Replica, Vector 저장소, 색인 작업과 네트워크 호출이 추가된다.

### 5.4. Attention과 Context

Attention은 현재 Token이 다른 Token의 정보를 어느 정도 반영할지 계산한다. Context는 한 요청에서 모델이 참조하는 Token 범위다.

Context가 길어지면 입력 처리 연산과 Attention 관련 메모리가 증가한다. 생성형 추론에서는 Layer별 Key와 Value 상태를 KV Cache에 보관하므로 긴 Context와 높은 동시성이 VRAM을 압박한다.

### 5.5. 모델 Artifact

모델을 실행하려면 Weight 한 파일만 필요한 것이 아니다.

| Artifact | 역할 | 누락·불일치 영향 |
| --- | --- | --- |
| Model config | Layer, Hidden size, Attention 구조 등 | Weight를 올바르게 구성하지 못함 |
| Weight shard | 학습된 Parameter | 모델 자체를 실행할 수 없음 |
| Tokenizer와 Vocabulary | Text↔Token 변환 | 입력·출력 의미 손상 |
| Generation config | 종료 Token, Sampling 기본값 등 | 출력 특성이나 종료 동작 변화 |
| Adapter | LoRA 등 추가 학습분 | 도메인·업무 동작이 빠짐 |
| Quantization config/metadata | Scale, Zero-point, Group 등 | 올바른 복원·Kernel 실행 실패 |

운영 시 이 Artifact들을 하나의 Version 단위로 고정하고 무결성을 검증해야 한다.

## 6. 모델 학습과 활용 방식

### 6.1. Pre-training

대규모 Dataset으로 모델의 기본 Weight를 만드는 과정이다. 모든 Parameter의 Gradient와 Optimizer State, Activation을 보관하므로 추론보다 훨씬 많은 GPU 메모리와 GPU 간 통신이 필요하다.

### 6.2. Fine-tuning

사전 학습된 모델을 특정 Domain이나 작업에 맞춰 추가 학습한다.

- **Full Fine-tuning**은 전체 Weight를 갱신한다. 높은 메모리와 Checkpoint 저장 공간이 필요하다.
- **PEFT**는 일부 Parameter만 학습한다. 대표적으로 LoRA는 작은 Low-rank Adapter를 학습해 GPU 메모리와 저장량을 줄인다.
- **QLoRA**는 Base Model을 저정밀로 고정하고 LoRA Adapter를 학습해 제한된 VRAM에서 큰 모델을 조정할 수 있게 한다.

Fine-tuning은 모델에 새로운 사실을 안전하게 저장하는 만능 수단이 아니다. 행동, 형식, 용어와 Task 적응에는 적합할 수 있지만 자주 바뀌는 지식은 RAG가 더 관리하기 쉬울 수 있다.

### 6.3. RAG

Retrieval-Augmented Generation은 질의와 관련된 외부 문서를 검색해 Prompt Context에 포함한 뒤 모델이 답변하도록 구성하는 방식이다. 모델 종류가 아니라 검색과 생성 모델을 결합한 실행 구조다.

```text
문서 → Embedding → Vector Index

질문 → Query Embedding → 검색/Rerank
     → 검색 결과를 Context에 추가
     → LLM 호출 → 답변
```

RAG는 Weight 재학습 없이 지식을 교체할 수 있지만 Embedding 서비스, Vector DB, Reranker, 데이터 동기화와 추가 네트워크 지연이 생긴다. 검색 문서가 길어지면 Context와 KV Cache도 증가한다.

### 6.4. Agent

Agent는 모델 출력을 바탕으로 도구를 선택하고, 결과를 다시 모델에 전달하며 목표를 수행하는 애플리케이션 실행 구조다. Agent 자체가 새로운 모델 종류는 아니다.

한 사용자 요청이 여러 번의 모델·검색·DB·외부 API 호출로 확장될 수 있다. 따라서 단일 모델 지연보다 전체 호출 횟수, Timeout, 재시도, 상태 저장, 비용과 Tool 권한이 중요하다.

### 6.5. vLLM의 위치

vLLM은 LLM 모델이나 학습 방법이 아니라 모델 Weight를 GPU에 적재하고 요청을 Batch 처리해 API로 제공하는 추론·서빙 Runtime이다. Ollama, llama.cpp, LM Studio, Docker Model Runner도 실행 도구에 해당한다. 설치와 호출 방법은 모델 실행 문서에서 정리한다.

## 7. 양자화 모델

### 7.1. 양자화가 필요한 이유

양자화는 Weight 또는 Activation을 더 적은 bit로 표현해 저장 공간과 메모리 트래픽을 줄이는 방법이다.

```text
낮은 Weight bit 수
→ 모델 파일 감소
→ 필요한 RAM/VRAM 감소
→ 더 작은 GPU 또는 적은 GPU에 적재 가능
→ Memory Bandwidth 부담 감소 가능
```

하지만 낮은 bit 수가 항상 더 빠른 것은 아니다. 해당 GPU와 Runtime에 최적화된 Kernel이 없거나 Dequantization 비용이 크면 속도가 같거나 느려질 수 있다.

### 7.2. 정밀도와 메모리

| 표현 | Weight당 이론 크기 | 일반적 의미 |
| --- | ---: | --- |
| FP32 | 4 bytes | 높은 정밀도, 큰 메모리 사용 |
| FP16/BF16 | 2 bytes | 학습·추론에서 널리 쓰이는 저정밀 부동소수점 |
| FP8 | 1 byte | 지원 Hardware/Framework에서 학습·추론 최적화에 사용 |
| INT8 | 1 byte | 주로 추론 메모리와 대역폭 절감 |
| INT4 계열 | 약 0.5 bytes | 더 큰 압축, 품질·Kernel 지원 검증 필요 |

표의 크기는 Weight만 계산한 하한이다. Scale, Zero-point, Group metadata, Padding, KV Cache와 Runtime Workspace가 별도로 필요하다.

### 7.3. 무엇을 양자화하는가

- **Weight-only**: Weight는 INT8/INT4 등으로 저장하고 연산 중 일부는 FP16/BF16으로 처리한다.
- **Weight + Activation**: Weight와 중간 Activation을 함께 낮은 정밀도로 처리한다. Hardware와 Kernel 지원 영향이 더 크다.
- **KV Cache Quantization**: 요청별 Cache 정밀도를 낮춰 긴 Context와 동시성을 늘릴 수 있으나 품질과 Runtime 지원을 검증해야 한다.

### 7.4. 언제 양자화하는가

- **Post-Training Quantization(PTQ)**은 학습이 끝난 Weight를 변환한다. Calibration Dataset이 필요한 방법도 있다.
- **Quantization-Aware Training(QAT)**은 학습 중 양자화 오차를 반영한다. Training 비용은 증가하지만 저정밀 품질을 개선할 수 있다.
- **QLoRA**는 양자화된 Base Model을 고정하고 별도 Adapter를 학습한다. 이미 배포용으로 양자화된 모든 파일을 그대로 Full Fine-tuning한다는 의미가 아니다.

### 7.5. 방법, 파일 형식, 실행 도구를 구분한다

| 이름 | 종류 | 의미 |
| --- | --- | --- |
| GPTQ | 양자화 방법 | Calibration 기반의 Post-training Weight Quantization |
| AWQ | 양자화 방법 | 중요한 Activation과 Weight 특성을 고려한 Weight Quantization |
| GGUF | 파일 형식과 실행 생태계 | 여러 정밀도·양자화 Tensor와 Metadata를 담을 수 있음 |
| bitsandbytes | Library/Runtime | Transformers에서 8-bit·4-bit Loading과 저정밀 연산 지원 |
| Safetensors | Tensor 저장 형식 | 양자화 여부 자체를 뜻하지 않음 |

`GGUF=4-bit`, `Safetensors=비양자화`처럼 확장자만으로 판단하면 안 된다. 실제 Tensor dtype, Quantization config와 Runtime 호환성을 확인해야 한다.

### 7.6. 양자화 선택 시 확인할 항목

- 목표 GPU/CPU가 해당 dtype과 Kernel을 효율적으로 지원하는가?
- 사용할 Runtime이 모델 Architecture와 양자화 방법을 지원하는가?
- 품질 평가가 원본과 동일한 Prompt·Dataset으로 수행됐는가?
- Weight 절감 후에도 KV Cache와 Activation이 VRAM에 들어가는가?
- 처리량뿐 아니라 TTFT와 출력 Token/sec도 개선되는가?
- Adapter 병합, Tensor Parallel과 Speculative Decoding 같은 기능과 호환되는가?

## 8. 개념 위치 정리

| 용어 | 분류 | 인프라에서 확인할 것 |
| --- | --- | --- |
| NLU/NLG | 언어 처리 문제 영역 | 출력 형태, Batch, 지연, 생성 상태 |
| CNN/RNN/Transformer | 신경망 Architecture | 연산 병렬성, 메모리, 지원 Kernel |
| SLM/sLLM/LLM | 상대적인 모델 규모 표현 | 실제 Parameter, 정밀도, Context |
| Fine-tuning/LoRA/QLoRA | 모델 적응 방법 | Training Memory, Checkpoint, GPU 수 |
| RAG | 검색과 생성을 결합한 구조 | Embedding, Vector DB, Context, 지연 |
| Agent | 모델과 Tool을 반복 호출하는 구조 | 호출 횟수, 상태, Timeout, 권한, 비용 |
| vLLM/Ollama/llama.cpp | 모델 실행·서빙 Runtime | 모델 형식, Hardware, 동시성, API |
| GPTQ/AWQ | 양자화 방법 | Kernel, 품질, Runtime 호환성 |
| GGUF/Safetensors | Artifact 형식 | Tensor dtype, Metadata, Loader 호환성 |

## 9. 정리

- NLU는 모델 체급이 아니라 언어의 의미를 해석하는 문제 영역이다.
- BERT 계열과 LLM 모두 NLU를 수행할 수 있지만 출력과 실행 특성이 다르다.
- SLM, sLLM, LLM 명칭보다 Parameter, 정밀도, Context와 Batch가 인프라 산정에 중요하다.
- Fine-tuning은 Weight를 조정하는 학습 방법이고 RAG와 Agent는 여러 구성요소를 결합한 실행 구조다.
- vLLM은 모델이 아니라 추론·서빙 Runtime이다.
- 양자화는 RAM/VRAM 요구량을 줄일 수 있지만 품질과 Hardware/Runtime Kernel 지원을 함께 검증해야 한다.

## 10. References

- Google Cloud, [Cloud Natural Language documentation](https://docs.cloud.google.com/natural-language/docs)
- Google Cloud, [Natural Language API basics](https://docs.cloud.google.com/natural-language/docs/basics)
- Vaswani et al., [Attention Is All You Need](https://papers.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html), NeurIPS 2017
- Devlin et al., [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding](https://research.google/pubs/bert-pre-training-of-deep-bidirectional-transformers-for-language-understanding/), NAACL 2019
- Lewis et al., [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html), NeurIPS 2020
- Hu et al., [LoRA: Low-Rank Adaptation of Large Language Models](https://www.microsoft.com/en-us/research/publication/lora-low-rank-adaptation-of-large-language-models/), ICLR 2022
- Dettmers et al., [QLoRA: Efficient Finetuning of Quantized LLMs](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract.html), NeurIPS 2023
- Frantar et al., [GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers](https://arxiv.org/abs/2210.17323)
- Lin et al., [AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration](https://arxiv.org/abs/2306.00978)
- Hugging Face, [Transformers quantization](https://huggingface.co/docs/transformers/main_classes/quantization)
