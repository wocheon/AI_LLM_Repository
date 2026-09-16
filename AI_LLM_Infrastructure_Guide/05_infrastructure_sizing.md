# AI 모델 인프라 스펙 산정

인프라 산정은 Parameter 수를 GPU VRAM으로 바꾸는 한 번의 계산이 아니다. Model Artifact와 실행 방식을 고정하고, Memory 수용 여부와 목표 Workload 처리 여부를 각각 계산한 뒤 같은 조건의 Benchmark로 검증하는 작업이다.

## 1. 산정에 필요한 입력값

### 1.1. Model Parameter와 Architecture

Model 이름만으로는 필요한 자원을 결정할 수 없다. 같은 Parameter 규모라도 Architecture와 Artifact에 따라 Weight, KV Cache, 연산량과 Runtime 지원 범위가 달라진다.

먼저 다음 값을 Model Card, `config.json`, Weight Index와 실제 Tensor Metadata에서 수집한다.

| 입력값 | 확인 내용 | 산정에 미치는 영향 |
| --- | --- | --- |
| Model Revision | Commit, Tag, Checksum | 같은 이름의 Artifact 변경을 구분한다. |
| 전체 Parameter 수 | Embedding, Expert, Output Head 포함 여부 | Weight와 학습 상태의 하한을 정한다. |
| 활성 Parameter 수 | MoE 요청에서 Token당 선택되는 Expert | 주로 요청당 연산량에 영향을 준다. |
| Layer 수 | Attention 또는 Cache를 갖는 Layer | KV Cache와 Activation이 증가한다. |
| Hidden Size | Model 내부 표현 차원 | 연산량과 Activation에 영향을 준다. |
| Attention Head 수 | Query Head 구성 | Attention 연산과 Tensor Parallel 제약에 영향을 준다. |
| KV Head 수와 Head Dimension | MHA, GQA, MQA 구분 | Token당 KV Cache 크기를 정한다. |
| Context 상한 | Model 한계와 운영 설정을 구분 | 최대 요청 Memory와 Admission Policy를 정한다. |
| Modality | Text, Image, Audio, Video | Encoder Weight, 입력 Token과 전처리 자원이 추가된다. |

MoE Model은 모든 Expert Weight를 Memory에 적재하면서 한 Token에는 일부 Expert만 사용할 수 있다. 따라서 `전체 Parameter=Memory`, `활성 Parameter=주요 Compute`라는 두 값을 구분한다. Weight Tying, 일부 Layer의 Sliding Window Attention, Cross-attention과 State Space 계열 Cache처럼 일반 Transformer 산식과 다른 구조도 실제 설정에서 확인한다.

Parameter 수가 문서에 반올림되어 있으면 실제 Weight 파일 또는 Tensor를 합산한 값이 더 정확하다. `8B`라는 이름이 정확히 8,000,000,000개의 동일 dtype Parameter를 뜻한다고 가정하지 않는다.

### 1.2. Weight Precision과 Quantization

`Model dtype` 하나로 모든 Tensor의 저장 형식을 표현할 수 없다. 다음 항목을 따로 기록한다.

- Weight 저장 dtype과 실행 시 dtype
- Quantization 방식, bit 수, Group Size와 Scale·Zero-point Metadata
- 계산에 사용하는 dtype과 Accumulator dtype
- KV Cache dtype
- 학습 시 Gradient, FP32 Master Weight와 Optimizer State dtype
- 양자화하지 않는 Embedding, Normalization, Output Head와 Adapter

예를 들어 4-bit Weight를 사용해도 KV Cache와 Activation은 BF16일 수 있다. 반대로 KV Cache만 FP8로 낮출 수도 있다. 파일 확장자나 `Q4`, `INT8`이라는 Label 대신 Runtime이 실제로 선택한 Kernel과 Tensor dtype을 확인한다.

용량 단위도 고정한다.

```text
1 GB  = 1,000,000,000 bytes
1 GiB = 1,073,741,824 bytes
```

Model 제공자가 표시한 GB, 운영체제와 GPU 도구가 표시한 GiB 또는 MiB를 섞으면 수 %의 오차가 생긴다. 산정표 내부 계산은 bytes로 유지하고 마지막에 같은 단위로 변환한다.

### 1.3. Context, Batch와 동시 요청

생성형 Serving은 `최대 Context × 최대 동시 사용자`만으로 산정하면 실제 Traffic을 과대 또는 과소평가하기 쉽다. 운영 Log나 예상 Traffic에서 다음 분포를 만든다.

- 초당 도착 요청 수와 Burst 구간
- 입력 Token과 출력 Token의 평균, p50, p95, p99, 최대값
- 동시에 실행 중인 Sequence 수와 대기 중인 요청 수
- Prompt Prefix 재사용률
- Streaming 연결 유지 시간과 취소율
- Beam, `n`, `best_of`처럼 요청 하나가 만드는 Sequence 수
- Image 수·해상도, Audio 길이처럼 Token 외 입력 크기

`Context Length`는 보통 입력 Token과 현재까지 생성한 Token의 합이다. 설정된 최대 Context는 Admission 상한이고 모든 요청의 실제 Cache 사용량은 아니다. 반면 Static Cache나 사전 할당 방식은 실제 사용량보다 설정 상한의 영향을 더 크게 받을 수 있다.

Batch도 구분해서 기록한다.

| 구분 | 의미 | 주요 자원 영향 |
| --- | --- | --- |
| Offline Batch | 한 번의 Forward Pass에 넣는 Sample 수 | Activation과 입력 Tensor |
| Continuous Batch | Serving Runtime이 한 Iteration에 함께 처리하는 Sequence | KV Cache, Scheduler와 Throughput |
| Prefill Token Budget | 한 번에 처리하는 Prompt Token 총량 | Prefill Activation과 Peak VRAM |
| Training Micro-batch | GPU 한 장이 한 Step에 처리하는 Sample | Activation Memory |
| Effective Batch | Micro-batch × Gradient Accumulation × Data Parallel 수 | 학습 통계와 전체 처리량 |

### 1.4. Training과 Inference 구분

Inference는 주로 Weight, KV Cache, Activation과 Runtime Workspace를 사용한다. Training은 여기에 Gradient, Optimizer State, 선택적으로 FP32 Master Weight와 역전파용 Activation을 추가한다.

| 실행 형태 | Parameter 상태 | 요청·Batch 상태 | 추가 고려사항 |
| --- | --- | --- | --- |
| Encoder 추론 | Weight | 입력 Tensor와 Activation | Batch와 Sequence Length |
| 생성형 추론 | Weight | Activation과 요청별 KV Cache | 입력·출력 길이, 동시성 |
| Full Fine-tuning | 전체 Weight, Gradient, Optimizer State | 역전파용 Activation | 분산 Sharding과 Checkpoint |
| LoRA | Base Weight와 Adapter, Adapter 학습 상태 | 역전파용 Activation | Base Weight는 여전히 적재됨 |
| QLoRA | 양자화 Base Weight와 Adapter 학습 상태 | 역전파용 Activation | Dequantization Buffer와 Kernel 지원 |

Training 산정에는 모델 수용 여부 외에 목표 완료 시간도 필요하다. Dataset Sample 수, 평균 Sequence Length, Epoch 수, 목표 Step/sec, Checkpoint 주기와 재시작 허용 시간을 입력값에 포함한다.

### 1.5. 성능 목표와 운영 조건

GPU 수를 결정하려면 Memory 조건과 별도로 통과 기준을 정해야 한다.

- Serving: p95/p99 TTFT, TPOT 또는 Inter-token Latency, End-to-end Latency, 요청/초, 출력 Token/초, Timeout과 오류율
- Offline Inference: 완료 시간, Sample/초와 비용 상한
- Training: Step Time, Token/초, 목표 완료 시간, Scaling Efficiency와 Checkpoint 시간
- 운영: 동시 배포 Version 수, 장애 시 유지해야 할 Capacity, Cold Start와 복구 시간

평균 Latency만 목표로 두면 긴 Prompt와 Burst에서 Queue가 증가하는 상황을 놓친다. `처리량 최대화`와 `Latency SLO 이내의 유효 처리량`을 구분한다.

## 2. VRAM 산정

Inference의 Peak VRAM은 다음 구성으로 분해한다.

```text
Peak VRAM
≈ Weight
+ KV Cache
+ Activation과 입력·출력 Tensor
+ Runtime Workspace와 통신 Buffer
+ Memory Allocator 예약·단편화
+ 같은 GPU를 사용하는 다른 Process
```

항목을 합친 결과는 후보 Hardware를 거르는 계산값이다. Runtime이 미리 예약하는 Cache, CUDA Graph, Kernel Workspace와 순간 Peak는 실행하지 않고 정확히 알기 어렵다.

### 2.1. Weight Memory

동일 dtype으로 저장된 Dense Weight의 이론적 하한은 다음과 같다.

```text
Weight bytes = Parameter 수 × Parameter당 bit 수 ÷ 8
```

대표적인 하한은 다음과 같다.

| 저장 형식 | Parameter당 이론값 | 10억 Parameter당 용량 |
| --- | ---: | ---: |
| FP32 | 4 bytes | 약 3.73 GiB |
| FP16/BF16 | 2 bytes | 약 1.86 GiB |
| INT8/FP8 | 1 byte | 약 0.93 GiB |
| 4-bit | 0.5 byte | 약 0.47 GiB |

이 표는 Weight Payload의 하한이다. Quantization Metadata, Padding, 비양자화 Layer, Tensor 정렬과 Runtime 변환본은 별도다. 따라서 다음 순서로 값을 보정한다.

1. 실제 Weight Shard의 논리적 Tensor 크기를 합산한다.
2. Load 후 선택된 dtype과 Dequantization 여부를 확인한다.
3. GPU별 Weight 배치와 복제되는 Layer를 확인한다.
4. Adapter, Draft Model, Reranker처럼 같은 Process가 추가로 적재하는 Weight를 더한다.

Disk의 Artifact 크기는 압축, Serialization과 Sharding 때문에 VRAM Weight 크기와 같지 않을 수 있다. 반대로 Load 과정에서 원본과 변환본이 동시에 존재하면 RAM 또는 VRAM Peak가 최종 상태보다 커질 수 있다.

### 2.2. KV Cache

일반적인 Autoregressive Transformer의 KV Cache 하한은 다음과 같이 근사할 수 있다.

```text
Token당 KV bytes
= Layer 수 × 2(K와 V) × KV Head 수 × Head Dimension × KV dtype bytes

전체 KV bytes
= 모든 활성 Sequence의 Resident Token 수 합 × Token당 KV bytes
```

모든 요청 길이가 같다는 단순 조건에서는 다음과 같다.

```text
전체 KV bytes
= 동시 Sequence 수 × Sequence당 Resident Token 수
  × Layer 수 × 2 × KV Head 수 × Head Dimension × KV dtype bytes
```

MHA에서는 KV Head 수가 Attention Head 수와 같지만 GQA와 MQA에서는 더 작다. GQA Model에 전체 Query Head 수를 넣으면 Cache를 과대 계산한다. 반대로 Beam Search와 다중 출력은 요청 하나가 여러 Sequence 상태를 만들 수 있다.

다음 항목은 단순 산식을 바꾼다.

- Sliding Window, Chunked 또는 Hybrid Attention Layer
- Cross-attention Cache와 Multimodal Encoder 상태
- Prefix Cache의 공유 Block과 Cache Hit 비율
- Paged Cache의 미사용 Tail, Block Metadata와 내부 단편화
- Runtime의 KV Cache 사전 할당, CPU Offload 또는 KV Quantization
- Tensor Parallel에서 KV Head를 Shard 또는 Replicate하는 방식

산식으로 하한을 계산한 뒤 Runtime 시작 Log의 `KV cache size in tokens`, 최대 동시성, GPU별 Cache 할당량과 실제 Cache 사용 Metric으로 교정한다. 대기 Queue의 요청은 아직 KV Cache를 사용하지 않을 수 있으므로 `연결 수`와 `활성 Sequence 수`를 같은 값으로 보지 않는다.

### 2.3. Activation과 Runtime Workspace

Activation은 Model 구조, Kernel, Batch와 Sequence Length에 따라 달라진다. 생성형 추론에서는 특히 다음 조건이 Peak를 만든다.

- 긴 Prompt 여러 개를 동시에 처리하는 Prefill
- 높은 Prefill Token Budget 또는 Encoder Batch
- 큰 Vocabulary의 Logits와 다중 Candidate
- Multimodal Encoder의 Image·Audio Tensor
- Attention Backend와 Fused Kernel의 임시 Workspace
- CUDA Graph Capture와 Compile된 Shape별 Buffer
- Tensor Parallel의 Collective Communication Buffer

KV Cache는 요청 수명 동안 비교적 오래 유지되지만 Activation과 Workspace는 연산 구간의 순간 Peak다. Idle 상태의 VRAM이나 Weight Load 직후 값만 측정하면 이 Peak를 놓친다.

정확하지 않은 고정 배수 대신 목표 입력 길이와 Batch를 실제 Runtime에 넣어 측정한다. 먼저 단일 요청에서 Weight와 기본 Workspace를 확인하고, 긴 Prefill, 동시 Decode와 혼합 Traffic 순서로 Peak를 측정하면 증가 원인을 구분하기 쉽다.

### 2.4. Training Memory

Training Memory는 전체 Parameter와 실제 학습하는 Parameter를 분리해 계산한다.

```text
Model-state bytes
≈ 전체 Parameter × 실행 Weight bytes
+ 학습 Parameter × (
     Master Weight bytes
   + Gradient bytes
   + Parameter당 Optimizer State bytes
  )
```

일반적인 FP16/BF16 Mixed Precision과 Adam 계열의 한 구성은 다음 항목을 가질 수 있다.

| 항목 | 적용 대상 | 예시 하한 |
| --- | --- | ---: |
| 실행 Weight | 전체 Parameter | 2 bytes/Parameter |
| FP32 Master Weight | 학습 Parameter | 4 bytes/Parameter |
| FP32 Gradient | 학습 Parameter | 4 bytes/Parameter |
| Adam 1차·2차 상태 | 학습 Parameter | 8 bytes/Parameter |

전체 Parameter를 학습하고 이 항목을 모두 유지하면 Activation을 제외하고 약 18 bytes/Parameter다. 이것은 보편 상수가 아니다. Framework가 별도 Master Weight를 만들지 않거나 Gradient dtype, Optimizer와 Precision이 다르면 값도 달라진다.

추가로 다음 Memory를 더한다.

- Backward까지 보존하는 Activation
- Loss, Logits와 Temporary Tensor
- Gradient Bucket과 Collective Buffer
- FSDP·ZeRO의 All-gather 시점 Parameter와 Prefetch Buffer
- Quantized Training의 Scale, Dequantization Workspace와 Adapter
- Checkpoint 생성·직렬화 과정의 임시 Memory

Activation은 Micro-batch, Sequence Length, Hidden Size와 Layer 수에 크게 좌우된다. Activation Checkpointing은 일부 Activation을 저장하지 않고 Backward에서 다시 계산해 Memory를 줄이지만 Step Time을 늘릴 수 있다. Gradient Accumulation은 Effective Batch를 유지하면서 Micro-batch Memory를 낮추지만 Step 수와 통신 시점이 달라진다.

Data Parallel은 Model State를 GPU마다 복제한다. FSDP와 ZeRO는 설정에 따라 Optimizer State, Gradient와 Parameter를 Rank에 나누지만 모든 Buffer가 완벽히 `GPU 수`로 나뉘지는 않는다. 가장 큰 Layer의 일시적 All-gather와 Rank별 Peak를 포함해 Framework Estimator와 실행 측정을 함께 사용한다.

### 2.5. 여유 공간과 Memory Fragmentation

GPU의 명목 VRAM 전체를 Application이 사용할 수 있다고 가정하지 않는다. Driver와 Context, Display Process, Monitoring Agent, 다른 Container가 일부를 사용하며 Runtime Allocator가 재사용을 위해 Memory를 예약할 수 있다.

```text
사용 가능 VRAM
= 실제 장치 Total
- 상시 System·다른 Process 사용량
- 운영 Safety Margin

통과 조건
= 측정한 Application Peak VRAM < 사용 가능 VRAM
```

Safety Margin을 모든 Model에 같은 비율로 고정하지 않는다. 다음 변동폭을 측정해 결정한다.

- p99 입력 길이와 Burst에서의 Peak 증가
- Runtime 시작, Warm-up과 Graph Capture 구간
- Allocated Memory와 Reserved Memory 차이
- 장시간 실행 후 단편화와 Cache 변화
- Model Reload 또는 Rolling Update 중 중복 적재 여부

PyTorch의 `memory_allocated`는 Tensor가 점유한 Memory이고 `memory_reserved`는 Caching Allocator가 관리하는 영역이다. 둘 모두 `nvidia-smi`의 Process Memory와 다를 수 있다. Application Metric과 장치 관측값을 같이 기록한다. OOM 직전까지 Cache를 크게 잡는 설정은 정상 부하 처리량을 높일 수 있지만, 비정상적으로 긴 요청이나 같은 GPU의 다른 Process에 대한 여유를 줄인다.

## 3. GPU 산정

### 3.1. 단일 GPU 수용 여부

단일 GPU 후보는 다음 두 조건을 모두 만족해야 한다.

1. Model Load, 목표 Context·Batch와 최악 조건에 가까운 요청에서 OOM이 없다.
2. 목표 Latency와 처리량을 동시에 만족한다.

Weight만 들어가는 GPU는 `실행 가능` 후보가 아니다. 2절에서 계산한 모든 항목을 GPU의 실제 사용 가능 VRAM과 비교한다. GPU Partition을 사용한다면 물리 GPU 전체가 아니라 할당된 Partition의 VRAM과 Compute를 사용한다.

Multi-GPU의 Memory 기준 최소 수는 다음 식으로 대략 거를 수 있다.

```text
GPU 수 하한 ≈ ceil(Shard 가능한 Memory ÷ GPU당 Shard 가능 공간)
```

실제 통과 조건은 Rank마다 따로 계산한다.

```text
Rank별 Peak
= Rank별 Shard Memory
+ Rank마다 복제되는 Memory
+ Rank별 Activation·Workspace·통신 Buffer
< 해당 GPU의 사용 가능 VRAM
```

GPU VRAM 총합만 비교하면 GPU 0의 추가 Output 처리, 분할되지 않는 Embedding, 가장 큰 Layer와 불균등 Shard를 놓칠 수 있다. Runtime이 Model Architecture와 선택한 Parallel 크기를 지원하는지도 먼저 확인한다.

### 3.2. Compute와 Memory Bandwidth

VRAM은 실행 가능 여부를 우선 결정한다. 실행 속도는 GPU Compute, Memory Bandwidth, Tensor Core dtype 지원, Kernel과 Workload Shape가 함께 결정한다.

- 긴 Prompt의 Prefill과 Training Matrix 연산은 Compute 활용도가 높아질 수 있다.
- 한 Token씩 Weight와 KV Cache를 반복해서 읽는 Decode는 Memory Bandwidth의 영향을 크게 받을 수 있다.
- 작은 Model·Batch는 CPU Tokenization과 Kernel Launch 때문에 GPU를 충분히 사용하지 못할 수 있다.
- Quantization은 Memory Traffic을 줄일 수 있지만 Dequantization이나 미지원 Kernel Fallback이 이득을 줄일 수 있다.

Peak FLOPS나 명목 Memory Bandwidth로 Token/sec를 직접 환산하지 않는다. 먼저 이론 사양으로 후보를 좁히고 실제 Model, dtype, Runtime과 요청 분포로 Benchmark한다.

Serving Capacity는 Prefill과 Decode 수요를 나누어 본다.

```text
초당 입력 Token 수요 = 요청 도착률 × 요청당 평균 입력 Token
초당 출력 Token 수요 = 요청 도착률 × 요청당 평균 출력 Token
```

한 개의 합산 Token/sec가 두 조건을 모두 대표하지 않는다. TTFT는 Prefill과 Queue 영향을, TPOT는 Decode와 동시 실행 영향을 함께 보여준다. 목표 Latency를 만족한 가장 높은 요청 도착률을 해당 구성의 `유효 Capacity`로 사용한다.

안정된 구간의 평균 동시 요청은 Little's Law로 교차 확인할 수 있다.

```text
평균 System 내 요청 수 = 초당 수락 요청 수 × 평균 End-to-end 체류 시간(초)

평균 활성 Sequence 수
≈ 초당 수락 요청 수 × 평균 실제 실행·Streaming 시간(초)
```

첫 식은 Queue에서 기다리는 요청도 포함한다. KV Cache 산정에는 Runtime에 들어가 실제 실행 중인 Sequence의 체류 시간을 사용한다. Burst, 긴 Tail과 Admission Queue를 반영하려면 평균값만 쓰지 말고 Load Test에서 p95/p99 동시성과 Queue 시간을 확인한다.

### 3.3. Multi-GPU와 Interconnect

Model을 나눌 때는 GPU 수뿐 아니라 통신 경로를 함께 정한다.

| 구성 | Memory 배치 | 적합한 목적 | 확인할 통신 |
| --- | --- | --- | --- |
| Replica/Data Parallel | GPU 또는 Group마다 Weight 복제 | 독립 요청 처리량 | Training Gradient 동기화, Serving은 적음 |
| Tensor Parallel | Layer 내부 Weight와 연산 분할 | 한 Model 수용, 단일 요청 연산 분담 | Layer마다 Collective 발생 가능 |
| Pipeline Parallel | Layer 구간을 Stage로 분할 | 큰 Model 수용 | Stage 간 Activation, Pipeline Bubble |
| FSDP/ZeRO | 학습 상태를 Data Parallel Rank에 Shard | Training Memory 절감 | All-gather, Reduce-scatter |

한 Node 안에서도 GPU 쌍마다 NVLink 계열 연결 또는 PCIe 경로가 다를 수 있다. 여러 Node를 사용하면 NIC, RDMA, Switch와 Oversubscription이 요청 또는 Training Step의 Critical Path에 들어간다. `nvidia-smi topo -m`으로 배치를 확인하고 NCCL Test와 실제 Workload에서 Collective Bandwidth를 측정한다.

Model이 단일 GPU에 들어간다면 여러 독립 Replica가 Serving 처리량과 장애 격리에 유리할 수 있다. Model이 들어가지 않을 때는 Tensor/Pipeline Parallel Group 하나를 최소 Serving 단위로 본다. TP 4인 서비스의 장애 여유는 GPU 한 장을 추가하는 것만으로 확보되지 않을 수 있으며, 재구성 시간을 허용하지 않으면 여분의 4-GPU Group이 필요할 수 있다.

### 3.4. GPU 수 증가 시 통신 비용

GPU 수 증가 효과는 다음 값으로 기록한다.

```text
Speedup(N | B) = B개 GPU 실행 시간 ÷ N개 GPU 실행 시간
Scaling Efficiency(N | B) = Speedup(N | B) ÷ (N ÷ B)
```

`B`는 기준 GPU 수다. 단일 GPU에 Model이 들어가면 `B=1`이고, 들어가지 않으면 가장 작은 실행 가능한 GPU 수를 기준점으로 사용한다. 다음 요인이 Scaling Efficiency를 낮춘다.

- Tensor Parallel Collective와 Rank 동기화
- 작은 Local Batch 또는 Sequence
- Pipeline Stage 불균형과 Bubble
- Data Loading, CPU와 Storage 병목
- GPU·NIC NUMA 배치 오류
- 느린 Rank, Thermal·Power 제한과 Network 혼잡

GPU를 늘려 Latency가 조금 줄어도 GPU-hour와 요청당 비용이 더 크게 증가할 수 있다. Memory 수용을 위한 최소 Group 크기와 처리량을 위한 Replica 수를 분리해서 계산한다.

```text
필요 Replica Group 수
= ceil(목표 유효 요청률 ÷ Group당 검증된 유효 요청률)
```

여기에 Rolling Update와 장애 시 유지할 Capacity를 별도로 더하고, Load Balancer를 포함한 전체 구성에서 다시 검증한다.

## 4. CPU, RAM, Storage와 Network

### 4.1. CPU와 Tokenization

CPU는 Tokenization·Detokenization, Chat Template, JSON 처리, Image·Audio 전처리, Request Scheduling, DataLoader와 GPU Kernel 제출을 담당한다. GPU가 빨라질수록 CPU가 요청을 공급하지 못하는 현상이 더 잘 드러날 수 있다.

CPU Core 수는 Model Parameter로 계산하지 않는다. 목표 요청률에서 다음 값을 측정한다.

- 입력·출력 Token/sec와 전처리 Sample/sec
- Process·Thread·DataLoader Worker별 CPU 사용률
- Run Queue, Context Switch와 CPU Throttling
- p95 Tokenization 시간과 API Handler 시간
- NUMA Node별 CPU, RAM, GPU와 NIC 근접성

Benchmark Client를 Model Server와 같은 Host에서 실행하면 Client의 Tokenization과 Traffic 생성이 Server CPU를 빼앗을 수 있다. Capacity 검증에서는 Client를 별도 Host에 두거나 CPU 사용량을 분리한다.

Worker를 늘리면 CPU 처리량이 증가할 수 있지만 Process별 Model·Tokenizer와 Memory가 복제될 수 있다. Physical Core, SMT, Container CPU Limit과 실제 Thread Pool 크기를 함께 기록한다.

### 4.2. System RAM과 Model Loading

System RAM은 정상 실행 상태보다 Load와 전환 구간에서 더 많이 필요할 수 있다.

```text
Peak RAM
≈ Host에 유지하는 Weight·Offload State
+ Load·변환 중 임시 Weight와 가장 큰 Shard
+ Tokenizer와 Application Process
+ Dataset·Page Cache와 Pinned Memory
+ Request Queue와 전처리 Buffer
+ OS·Agent 여유
```

`RAM은 VRAM의 2배` 같은 고정 규칙을 사용하지 않는다. Low-memory Loader는 Weight를 순차 적재해 Peak RAM을 줄일 수 있고, 반대로 dtype 변환이나 여러 Worker의 동시 Load는 복제본을 만든다. Rolling Update 중 구·신 Model Process가 겹치는지도 확인한다.

CPU Offload를 사용하면 System RAM에 Offload Weight뿐 아니라 실행 중 이동 Buffer가 필요하다. Training에서 Optimizer Offload를 사용하면 Optimizer State와 Gradient의 Host RAM 요구량, Pinned Memory, CPU 연산 비용을 더한다. Swap 발생은 OOM을 늦출 수 있지만 Latency와 Step Time을 크게 흔들 수 있으므로 정상 Capacity로 간주하지 않는다.

### 4.3. Model·Dataset Storage

Storage 용량은 현재 Weight 파일 하나보다 넓게 잡는다.

```text
필요 Storage
≈ 현재 Model Artifact
+ Rollback용 Model Revision
+ Download·변환·압축 해제 임시 공간
+ Runtime Cache와 Compile Artifact
+ Dataset 원본·전처리본·Index
+ Checkpoint와 Optimizer State
+ Log·Metric 보존량
```

Training Checkpoint는 Model Weight만 저장할 때와 Optimizer·Scheduler·RNG State까지 저장할 때 크기가 다르다. 다음 값을 곱해 보존량을 계산한다.

```text
Checkpoint 공간
= Checkpoint 1개 실측 크기 × 동시에 보존할 개수
+ 저장 중 임시 파일과 업로드 재시도 여유
```

Capacity 외에 순차 읽기 처리량, IOPS와 유효 Network Storage Bandwidth를 측정한다.

```text
Model 전송 시간의 하한 ≈ Artifact bytes ÷ 유효 읽기·Network bytes/sec
Checkpoint 기록 시간의 하한 ≈ Checkpoint bytes ÷ 유효 쓰기 bytes/sec
```

작은 Shard가 매우 많으면 Metadata와 IOPS가, 큰 Shard 몇 개이면 단일 Stream 처리량과 실패 재시도 비용이 중요해진다. GPU 할당 후 원격 Download를 시작하는 구성은 Cold Start 동안 GPU가 유휴 상태로 과금될 수 있다.

### 4.4. API와 분산 통신 Network

단일 Node Serving의 API Traffic은 실제 직렬화된 Payload와 Streaming 구간에서 측정한다. Text Token 수만으로 Wire Bytes를 확정할 수 없으며 TLS, HTTP Header, JSON, Image와 Audio가 포함된다. 목표 요청률, 평균 Payload와 Burst를 사용해 Load Balancer, NIC와 Egress 용량을 검증한다.

분산 실행에서는 Application Traffic보다 GPU Collective가 훨씬 클 수 있다.

- Tensor Parallel: Forward 경로의 All-reduce 또는 All-gather
- Data Parallel Training: Gradient All-reduce
- FSDP·ZeRO: Parameter All-gather와 Gradient Reduce-scatter
- Expert Parallel: Token Routing을 위한 All-to-all
- Pipeline Parallel: Stage 사이 Activation 전송

NIC의 표기 속도를 유효 GPU 통신 대역폭으로 사용하지 않는다. Protocol Overhead, PCIe와 NUMA 경로, RDMA·GPUDirect 지원, Switch Oversubscription과 동시 Job의 영향을 포함해 Collective Benchmark를 수행한다. Model Download, Dataset Read와 Checkpoint Upload가 같은 Network를 공유하면 학습 또는 Serving Traffic과 경합하는지도 시험한다.

## 5. 제한된 환경의 최적화

### 5.1. Quantization

Quantization은 먼저 Weight Memory와 Memory Traffic을 줄인다. 다음 순서로 검토한다.

1. 목표 GPU와 Runtime이 Model Architecture용 Quantized Kernel을 지원하는지 확인한다.
2. 실제 Artifact와 비양자화 Module을 포함한 Load VRAM을 측정한다.
3. 긴 Context에서 KV Cache가 여전히 병목인지 확인한다.
4. 대표 Dataset으로 품질을 비교한다.
5. TTFT, TPOT와 동시 처리량을 원래 Precision과 비교한다.

4-bit Weight가 16-bit 대비 정확히 1/4의 전체 VRAM을 사용한다고 보지 않는다. KV Cache, Activation, Workspace는 그대로일 수 있고 Quantization Metadata와 Dequantization Buffer가 추가된다. KV Cache Quantization은 별도 기능이며 Runtime·GPU 지원과 Long-context 품질을 따로 검증한다.

### 5.2. Context와 Batch 조정

Memory가 부족할 때는 실제 Application 요구보다 큰 상한을 먼저 줄인다.

- `max_model_len`을 실제 입력·출력 정책에 맞춘다.
- 요청당 입력·출력 Token 상한과 전체 동시 Token Budget을 둔다.
- 긴 요청을 별도 Queue 또는 Replica로 분리한다.
- Offline 작업은 비슷한 길이끼리 묶어 Padding을 줄인다.
- Prefill Token Budget과 최대 동시 Sequence를 함께 조정한다.
- 학습은 Micro-batch를 줄이고 필요한 경우 Gradient Accumulation을 사용한다.

Batch를 줄이면 Peak Memory가 낮아지지만 GPU 활용률과 처리량도 낮아질 수 있다. Context를 줄이면 KV Cache뿐 아니라 Prefill 연산량과 Tail Latency도 달라진다. Prefix Cache는 반복 Prompt에 효과가 있지만 고유 Prompt만 들어오는 최악 조건의 Capacity를 대신하지 않는다.

### 5.3. CPU·Disk Offload

Offload는 더 느린 계층의 용량을 사용해 VRAM 수용 범위를 넓힌다.

```text
GPU VRAM ↔ PCIe·Coherent Link ↔ System RAM ↔ Storage
빠르고 작음                                크고 느림
```

Weight를 매 Layer 또는 Step마다 이동하면 Link Bandwidth와 Latency가 실행 경로에 들어간다. Disk Offload는 Page Cache와 NVMe 성능에도 의존한다. 다음을 함께 측정한다.

- Offload 후 최소 System RAM과 Pinned Memory
- Host↔Device와 Disk Read bytes/sec
- GPU Idle 구간과 PCIe Utilization
- 단일 요청 Latency, Token/sec와 Training Step Time
- Process 종료·재시작 시 Offload 파일 정리와 재사용 방식

Offload로 OOM이 사라졌다는 사실만으로 Serving Capacity를 충족했다고 판단하지 않는다. 반복 사용되는 서비스라면 더 작은 Model, 더 큰 VRAM 또는 Model Parallel이 비용과 Latency 면에서 나을 수 있다.

### 5.4. Tensor Parallel과 Pipeline Parallel

Tensor Parallel은 Layer 내부를 나눠 각 Token 처리 중 통신한다. Pipeline Parallel은 Layer 구간을 나눠 Activation을 다음 Stage로 보낸다. 둘 다 총 VRAM을 사용할 수 있게 하지만 단일 GPU Memory를 단순 합산한 것과 같지 않다.

선택할 때 다음을 확인한다.

- Attention·KV Head와 Hidden Dimension이 Parallel 크기로 분할 가능한가
- Rank별 Weight와 KV Cache가 실제로 어떻게 Shard되는가
- GPU 0 또는 마지막 Stage에 추가 Memory가 생기는가
- Stage별 Layer와 연산 시간이 균형적인가
- Intra-node·Inter-node Collective가 Latency 목표를 만족하는가
- Runtime이 조합하려는 Quantization과 Parallel 방식을 함께 지원하는가

한 Model의 Latency를 줄이기 위한 Model Parallel과 독립 요청 처리량을 늘리는 Replica를 혼동하지 않는다. 가능한 Parallel 크기를 각각 Benchmark하고 SLO를 만족하는 가장 작은 Group을 선택한다.

### 5.5. Model 또는 Runtime 변경

설정 조정의 비용이 너무 크면 Model이나 Runtime을 바꾸는 편이 낫다.

- 더 작은 Parameter 또는 GQA/MQA Model
- 필요한 Context에 맞는 Model
- Distillation된 Task 전용 Model
- 현재 GPU용 Kernel을 제공하는 Runtime과 Artifact 형식
- 생성이 필요 없는 작업을 위한 Encoder·분류 Model
- 긴 요청과 짧은 요청에 서로 다른 Model·Replica

작은 Model이 항상 더 빠르거나 품질이 낮은 것은 아니다. Target Dataset의 품질, 동일 Hardware에서의 성능과 운영 복잡도를 함께 비교한다. Runtime 변경 시 API 호환성뿐 아니라 Tokenizer, Chat Template, Sampling 기본값과 출력 품질도 고정한다.

## 6. 산정 예시

다음 계산은 방법을 설명하기 위한 가상 조건이다. 특정 Model이나 GPU 조합의 동작과 성능을 보장하지 않는다.

### 6.1. 단일 사용자 Local Inference

가상의 Dense Decoder Model 조건을 다음과 같이 둔다.

- Parameter: 8,000,000,000
- Weight: BF16
- Layer: 32
- KV Head: 8
- Head Dimension: 128
- KV Cache: BF16
- 활성 Sequence: 1
- Resident Token: 4,096

Weight 하한은 다음과 같다.

```text
8,000,000,000 × 2 bytes
= 16.00 GB
≈ 14.90 GiB
```

KV Cache 하한은 다음과 같다.

```text
4,096 × 32 × 2 × 8 × 128 × 2 bytes
= 536,870,912 bytes
= 0.50 GiB
```

Weight와 KV Cache만 합쳐도 약 15.40 GiB다. 16 GiB GPU에는 Activation, Workspace, Driver와 단편화 공간이 거의 남지 않으므로 BF16 후보에서 제외하고 24 GiB급 후보에서 실제 Load와 긴 Prompt를 시험한다. `Weight가 16 GB이므로 16 GB GPU면 된다`고 결론 내리지 않는 예다.

동일 Weight를 이론적 4-bit로 저장하면 Payload 하한은 약 3.73 GiB지만 Metadata, 비양자화 Tensor와 Runtime Buffer를 더해야 한다. 지원되는 Artifact가 있다면 4-bit 후보를 실제로 Load하고 품질, RAM, VRAM과 Token/sec를 측정한다. Local 사용이라도 Context 상한을 불필요하게 크게 잡지 않는다.

### 6.2. 다중 사용자 GPU Serving

가상의 Serving 조건을 다음과 같이 둔다.

- Parameter: 70,000,000,000, BF16 Weight
- Layer: 80, KV Head: 8, Head Dimension: 128, BF16 KV Cache
- Tensor Parallel: 4
- 요청 도착률: 평균 2 requests/sec
- 평균 End-to-end 체류 시간: 8초
- 평균 입력: 1,000 Token, 평균 출력: 250 Token

Little's Law로 Queue를 포함해 System 안에 머무는 평균 요청은 약 `2 × 8 = 16`이다. 여기서는 16개가 모두 Runtime에서 활성 상태이고 각 Sequence가 4,096 Resident Token을 점유하는 Stress 구간을 보수적으로 가정한다. 실제 산정에서는 Queue 시간과 실행 시간을 분리하고 운영 길이 분포로 활성 Sequence와 Resident Token을 교정한다.

```text
Weight 하한
= 70,000,000,000 × 2 bytes
≈ 130.39 GiB

KV Cache 하한
= 16 × 4,096 × 80 × 2 × 8 × 128 × 2 bytes
= 20.00 GiB
```

Weight와 KV Cache가 모두 4개 Rank에 균등 Shard된다는 이상적인 하한은 GPU당 약 `(130.39 + 20.00) ÷ 4 = 37.60 GiB`다. 4 × 48 GiB 구성을 후보로 둘 수 있지만 약 10.4 GiB의 명목 잔여 공간만 보고 확정하지 않는다. Runtime Workspace, 불균등 Layer, KV 복제 여부, Graph와 긴 Prefill Peak를 GPU별로 측정한다.

Workload 수요는 다음처럼 분리한다.

```text
평균 입력 수요 = 2 × 1,000 = 2,000 input tokens/sec
평균 출력 수요 = 2 × 250 = 500 output tokens/sec
```

실제 Traffic의 길이 분포와 Burst를 재현해 요청률을 단계적으로 올린다. p95 TTFT, TPOT와 오류율을 모두 만족한 최대 요청률을 이 4-GPU Group의 유효 Capacity로 기록한다. 목표 요청률을 한 Group이 처리하지 못하면 Group당 검증값으로 Replica 수를 계산한다. 장애 중에도 같은 Capacity가 필요하다면 48 GiB GPU 한 장이 아니라 완전한 TP Group 단위의 여유를 검토한다.

### 6.3. Fine-tuning

8B Model 전체를 FP16/BF16 실행 Weight, FP32 Master Weight·Gradient와 FP32 Adam 상태로 학습한다고 가정한다. 2.4절의 예시 구성에서는 Activation 제외 Model State가 다음과 같다.

```text
8,000,000,000 × 18 bytes
= 144.00 GB
≈ 134.11 GiB
```

이 값에는 Activation, Temporary Tensor와 분산 Buffer가 없다. GPU VRAM 총합이 134.11 GiB보다 크다는 이유만으로 Full Fine-tuning이 가능한 것은 아니다. Micro-batch와 Sequence Length를 정하고, FSDP·ZeRO 설정별 Rank Peak와 가장 큰 Layer의 일시 Memory를 Estimator 및 짧은 Training Run으로 확인한다.

같은 Base Model에 20,000,000개의 LoRA Parameter만 학습하고 Base와 Adapter 실행 Weight를 BF16으로 둔다고 가정하면 단순 하한은 다음과 같다.

```text
Base 실행 Weight
= 8,000,000,000 × 2 bytes
= 16.00 GB

Adapter 실행 Weight + Master Weight + Gradient + Adam State
= 20,000,000 × (2 + 4 + 4 + 8) bytes
= 0.36 GB

Model State 하한 합계
= 16.36 GB
≈ 15.24 GiB
```

LoRA는 Gradient와 Optimizer State를 크게 줄이지만 Base Weight와 Activation을 없애지 않는다. QLoRA는 Base Weight 항목을 더 낮출 수 있지만 Quantization Metadata, 비양자화 Module과 Dequantization Workspace가 추가된다. 최종 GPU 수는 목표 Sequence Length의 Activation Peak와 Step Time으로 결정한다.

Training 후보마다 다음 값을 함께 기록한다.

- Micro-batch, Gradient Accumulation, Data Parallel 수와 Effective Batch
- Activation Checkpointing 유무
- GPU별 Peak Allocated·Reserved Memory
- Step Time, Token/sec와 Scaling Efficiency
- Checkpoint 크기, 저장 시간과 재시작 성공 여부
- 목표 Epoch 또는 Step 완료 예상 시간

### 6.4. 산정값 Benchmark 검증

검증은 `들어가는가`와 `목표 부하를 처리하는가`를 나눠 수행한다.

1. Model Revision, Runtime·Driver Version, GPU와 설정을 고정한다.
2. Model Load와 Warm-up 중 Host RAM·VRAM Peak를 측정한다.
3. 단일 짧은 요청으로 결과와 기본 Latency를 확인한다.
4. 최대 입력, 최대 출력과 큰 Batch로 OOM 경계를 확인한다.
5. 실제 길이 분포, 도착률과 Burst를 재현해 SLO를 측정한다.
6. 장시간 실행에서 Memory 증가, Cache 회수와 Thermal Throttling을 확인한다.
7. Model Reload, Process 재시작, GPU 또는 Node 장애와 Rolling Update를 시험한다.

Serving 결과에는 최소한 다음 항목을 남긴다.

| 영역 | 기록값 |
| --- | --- |
| 재현 조건 | Model·Tokenizer Revision, Runtime Image, dtype, Quantization, Parallel 설정 |
| 입력 부하 | 요청 수, 도착률, Burst, 입력·출력 Token 분포, 동시성 |
| Latency | TTFT, TPOT, End-to-end의 p50·p95·p99 |
| Throughput | 완료 요청/초, 입력·출력 Token/초, SLO 이내 Goodput |
| 안정성 | OOM, 오류, Timeout, 취소, Queue 길이와 Cache Preemption |
| GPU | GPU별 Peak VRAM, SM·Memory Utilization, Power와 Throttling |
| Host | CPU, RAM, Disk I/O, Network, NUMA와 Container Limit |

GPU 장치 관측은 예를 들어 다음처럼 수집할 수 있다.

```bash
nvidia-smi --query-gpu=timestamp,index,memory.total,memory.used,utilization.gpu,utilization.memory,power.draw \
  --format=csv \
  --loop=1
```

PyTorch Workload는 `max_memory_allocated()`와 `max_memory_reserved()`를 요청 또는 Step 구간 전후에 기록한다. 이 값은 PyTorch Allocator 밖의 NCCL·CUDA 할당을 모두 보여주지 않으므로 `nvidia-smi` 또는 운영 Metric과 함께 본다.

vLLM 같은 Serving Runtime은 고정된 동시성 최대 처리량 시험과 목표 요청률 시험을 분리한다. 내장 Benchmark 도구를 사용한다면 현재 설치 Version의 `vllm bench serve --help`로 Option을 확인하고, Random 고정 길이만이 아니라 운영 Trace 또는 동일한 길이 분포를 사용한다.

최종 산정표에는 계산값, 실측 Peak, SLO를 만족한 Capacity와 남은 여유를 나란히 기록한다. Model, Runtime, GPU, Context 정책이나 Traffic 분포가 바뀌면 기존 결과를 그대로 재사용하지 않는다.

## 7. References

확인일: 2026-09-15

- Hugging Face Transformers, [GPU memory usage](https://huggingface.co/docs/transformers/model_memory_anatomy)
- Hugging Face Transformers, [KV cache strategies](https://huggingface.co/docs/transformers/main/en/kv_cache)
- Hugging Face Transformers, [Parameter-efficient fine-tuning](https://huggingface.co/docs/transformers/peft)
- Hugging Face Accelerate, [Big Model Inference](https://huggingface.co/docs/accelerate/main/usage_guides/big_modeling)
- PyTorch, [CUDA semantics: Memory management](https://docs.pytorch.org/docs/stable/notes/cuda.html#memory-management)
- DeepSpeed, [Memory Requirements](https://deepspeed.readthedocs.io/en/stable/memory.html)
- vLLM, [Configuration](https://docs.vllm.ai/en/latest/api/vllm/config/)
- vLLM, [Benchmark CLI](https://docs.vllm.ai/en/latest/benchmarking/cli/)
- NVIDIA, [Mastering LLM Techniques: Inference Optimization](https://developer.nvidia.com/blog/mastering-llm-techniques-inference-optimization/)
- NVIDIA, [NCCL Overview](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/overview.html)
- NVIDIA, [NCCL Performance and Tuning](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/troubleshooting/performance_and_tuning.html)
- NVIDIA, [`nvidia-smi` Documentation](https://docs.nvidia.com/deploy/nvidia-smi/)
