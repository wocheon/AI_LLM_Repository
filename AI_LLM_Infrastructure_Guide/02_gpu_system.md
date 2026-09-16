# GPU 시스템과 AI 연산

AI 모델이 GPU를 사용하는 이유와 실제 연산 경로를 정리한다. GPU만 보지 않고 VRAM, CPU, RAM, Storage, Network, 다중 GPU 연결과 Software Stack을 하나의 시스템으로 다룬다.

## 1. AI 모델에 GPU가 필요한 이유

### 1.1. AI 모델은 Tensor 연산을 반복한다

신경망의 입력, Weight와 중간 결과는 다차원 배열인 Tensor로 표현된다. Transformer의 Linear Layer, Attention과 MLP도 대부분 큰 행렬 곱과 벡터 연산으로 실행된다. 모델을 학습하거나 추론한다는 것은 이 연산을 많은 Layer와 Token에 걸쳐 반복하는 일이다.

행렬의 각 원소나 Tile 계산은 상당 부분 서로 독립적이다. GPU는 같은 종류의 연산을 많은 데이터에 동시에 적용하는 구조와 높은 메모리 대역폭을 제공하므로 이런 Workload에 적합하다.

```text
Token과 Weight
→ Tensor 구성
→ 행렬 곱, Attention, 정규화, 활성화 함수
→ 수많은 GPU Thread가 데이터를 나누어 처리
→ Layer마다 반복
```

GPU가 AI를 이해해서 빠른 것이 아니다. 병렬화할 수 있는 수치 연산의 양이 많고, Framework와 최적화 Library가 이를 GPU Kernel로 변환하기 때문에 빠른 것이다.

### 1.2. CPU와 GPU의 역할은 다르다

| 항목 | CPU | GPU |
| --- | --- | --- |
| 설계 중점 | 복잡한 제어 흐름과 낮은 지연의 범용 처리 | 많은 Thread를 사용한 높은 처리량 |
| 강한 작업 | OS, Scheduler, Tokenization, 분기, 직렬 작업 | 행렬 곱, Attention, 대규모 Tensor 연산 |
| 메모리 | 큰 System RAM, 범용 접근 | 상대적으로 제한된 VRAM, 높은 대역폭 |
| AI 시스템 역할 | 요청 처리와 GPU 작업 준비 | 모델의 주요 Training·Inference 연산 |

GPU는 CPU를 대체하지 않는다. CPU가 입력을 준비하고 GPU Kernel을 제출하며, GPU가 연산을 끝내도 결과를 후처리하고 Network로 반환하는 과정은 CPU에서 수행되는 경우가 많다. CPU가 부족하면 GPU가 다음 작업을 기다리므로 비싼 GPU가 유휴 상태가 될 수 있다.

### 1.3. 병렬화가 성능으로 이어지는 조건

GPU의 많은 연산 자원을 채우려면 한 번에 처리할 일이 충분해야 한다. Batch, Sequence Length와 Tensor 크기가 너무 작으면 Kernel 실행 준비와 데이터 이동 비용의 비중이 커진다. 반대로 큰 Batch는 GPU 활용률과 Throughput을 높일 수 있지만 Activation과 KV Cache가 증가하고 요청 지연이 길어질 수 있다.

성능은 다음 조건의 조합으로 결정된다.

- 연산이 충분히 큰 Tensor 단위로 묶이는가
- GPU가 지원하는 dtype과 최적화 Kernel을 사용하는가
- 필요한 데이터가 VRAM에 있고 재사용되는가
- CPU와 Storage가 입력 공급을 지연시키지 않는가
- 여러 GPU를 사용할 때 통신 시간이 연산 이득보다 작은가

### 1.4. GPU가 항상 필요한 것은 아니다

작은 분류 모델, 낮은 요청량, 느슨한 응답 시간, Edge 환경에서는 CPU나 다른 Accelerator가 비용과 운영 측면에서 더 적합할 수 있다. GPU 지원이 없는 연산이 많거나 모델이 자주 분기하면 GPU의 병렬 자원을 충분히 사용하지 못한다.

선택 기준은 모델 이름이 아니라 실제 Latency, Throughput, 메모리, 전력과 비용이다. 같은 모델도 Batch 1 대화형 추론과 대규모 Offline Batch 처리에서 적합한 장치가 달라질 수 있다.

## 2. Transformer가 GPU를 사용하는 방식

### 2.1. PyTorch에서 GPU까지의 실행 경로

PyTorch 같은 Framework에서 Tensor는 `device` 속성을 가진다. 모델과 입력 Tensor를 GPU Device로 이동하면 해당 연산이 Accelerator용 구현으로 Dispatch된다. NVIDIA 환경에서는 CUDA Kernel이나 cuBLAS·cuDNN 같은 Library가 실제 연산을 수행한다.

```text
Model Artifact ──Storage→ System RAM ──PCIe/NVLink-C2C 등→ VRAM
                                                   │
Request → CPU 전처리 → Input Tensor → Framework → GPU Kernel
                                                   │
Response ← CPU 후처리 ← Output Tensor ←────────────┘
```

GPU 작업은 CPU에 대해 비동기로 제출되는 경우가 많다. 매 연산마다 결과를 CPU로 읽거나 강제로 동기화하면 Pipeline이 끊기고 성능이 낮아진다. Tensor가 CPU와 GPU 사이를 반복해서 이동하지 않도록 실행 경로를 확인해야 한다.

### 2.2. Transformer의 주요 GPU 연산

Transformer는 하나의 연산만 실행하지 않는다.

- **Projection과 MLP**: 큰 행렬 곱이 중심이며 Tensor Core 활용 가능성이 높다.
- **Attention**: Query, Key, Value 생성과 행렬 곱, Softmax, 결과 Projection을 수행한다.
- **Normalization과 Activation**: 원소 단위 연산으로, 행렬 곱보다 Memory 접근이나 Kernel 실행 비용의 영향을 더 받을 수 있다.
- **Embedding과 Sampling**: 조회, 확률 계산과 Token 선택을 포함하며 일부 단계는 CPU 또는 별도 Kernel에서 실행될 수 있다.

Tensor Core는 지원 dtype과 Shape에서 행렬 곱·누산을 가속한다. 그러나 전체 실행 시간이 Tensor Core 연산으로만 구성되는 것은 아니므로 GPU의 Peak FLOPS만으로 모델 속도를 예측할 수 없다.

### 2.3. Training에서의 GPU 사용

Training은 Forward 결과만 계산하지 않고 Gradient를 구하는 Backward와 Weight 갱신까지 수행한다.

```text
Input Batch
→ Forward
→ Loss
→ Backward와 Gradient 계산
→ GPU 간 Gradient 동기화 가능
→ Optimizer State 갱신
→ 다음 Batch
```

Weight 외에 Activation, Gradient와 Optimizer State를 보관하므로 추론보다 메모리 요구량이 훨씬 크다. Activation Checkpointing, Mixed Precision, Gradient Accumulation과 Sharding은 메모리를 줄이거나 분산하지만 추가 계산이나 통신을 발생시킨다.

### 2.4. Inference에서의 GPU 사용

생성형 추론은 Prompt를 처리하는 Prefill과 Token을 하나씩 생성하는 Decode의 성격이 다르다. 생성 과정은 [AI 모델과 언어 Workload](01_ai_models.md#32-decoder-계열)에서 다루며, 여기서는 GPU 병목만 구분한다.

| 단계 | GPU 작업 | 흔한 병목 |
| --- | --- | --- |
| Model Loading | Weight를 Storage·RAM에서 VRAM으로 복사 | Storage, RAM, PCIe, VRAM Capacity |
| Prefill | Prompt Token을 큰 Tensor로 처리 | Compute, Attention, Context 크기 |
| Decode | 기존 KV Cache와 Weight를 읽으며 다음 Token 반복 생성 | Memory Bandwidth, KV Cache Capacity, Kernel 실행 비용 |

Prefill은 큰 행렬 연산을 만들기 쉬워 Compute 사용률이 높아질 수 있다. Decode는 요청당 한 번에 생성하는 Token 수가 작고 매 Step마다 Weight와 KV Cache를 읽으므로 Memory Bandwidth의 영향을 크게 받는 경우가 많다. 실제 병목은 Batch, Context, 모델 구조와 Runtime 최적화에 따라 달라진다.

### 2.5. Compute-bound와 Memory-bound

- **Compute-bound**는 계산 장치가 처리할 연산량이 병목인 상태다. Tensor Core 활용, 낮은 Precision과 큰 Batch가 도움이 될 수 있다.
- **Memory-bound**는 연산 장치보다 VRAM에서 데이터를 읽고 쓰는 속도가 병목인 상태다. Weight·KV Cache 크기 축소, Kernel Fusion과 데이터 재사용이 중요하다.
- **Launch 또는 CPU-bound**는 작은 Kernel을 너무 자주 제출하거나 CPU 전처리가 늦어 GPU가 기다리는 상태다. Batching, Graph Capture와 CPU 경로 최적화가 필요할 수 있다.

GPU Utilization 수치가 높다는 사실만으로 Tensor Core가 효율적으로 사용된다고 판단할 수 없다. Kernel별 시간, 연산량, 메모리 대역폭과 CPU 대기 시간을 함께 측정해야 한다.

## 3. GPU에서 확인할 자원

### 3.1. Compute 자원

NVIDIA GPU를 예로 들면 Streaming Multiprocessor(SM)가 Thread를 Warp 단위로 Scheduling한다. CUDA Core는 일반 산술 연산을, Tensor Core는 지원되는 작은 행렬 블록의 곱·누산을 가속한다.

확인할 값은 단순 Core 수보다 다음에 가깝다.

- Workload dtype에서의 실제 연산 성능
- Tensor Core와 해당 Precision 지원 여부
- GPU Architecture와 Compute Capability
- Runtime이 사용할 Kernel의 지원 여부
- 전력·온도 제한을 포함한 Sustained 성능

서로 다른 Precision의 TFLOPS를 직접 비교하거나 Graphics 성능을 AI 성능으로 간주해서는 안 된다.

### 3.2. VRAM Capacity

VRAM에는 Weight만 올라가지 않는다.

| 메모리 항목 | Training | 생성형 Inference |
| --- | --- | --- |
| Model Weight | 필요 | 필요 |
| Activation | Forward·Backward용으로 큼 | Prefill과 실행 중 사용 |
| Gradient | 필요 | 불필요 |
| Optimizer State | 필요 | 불필요 |
| KV Cache | 모델에 따라 사용 | Context와 동시 요청에 따라 증가 |
| Runtime Workspace | 필요 | 필요 |

Weight의 이론 크기는 `Parameter 수 × bit 수 ÷ 8`로 계산할 수 있지만 이것은 하한일 뿐이다. 고정된 `Weight의 1.5배` 같은 배수로 모든 모델의 VRAM을 산정하면 Context와 Batch 영향을 놓친다. 양자화와 메모리 항목은 [AI 모델과 언어 Workload](01_ai_models.md#7-양자화-모델)를 참고한다.

VRAM이 부족하면 단일 GPU 실행은 실패하거나 CPU Offload, Multi-GPU Sharding, Context·Batch 축소가 필요하다. Offload는 실행 가능성을 높이지만 PCIe 전송 때문에 속도가 크게 낮아질 수 있다.

### 3.3. Memory Bandwidth와 Cache

VRAM Capacity는 모델이 들어가는지를 결정하고, Memory Bandwidth는 데이터를 얼마나 빠르게 공급하는지를 좌우한다. 두 GPU의 VRAM 용량이 같아도 대역폭이 다르면 Decode 처리량이 달라질 수 있다.

GPU 내부 Cache와 Shared Memory는 자주 쓰는 데이터를 재사용해 외부 VRAM 접근을 줄인다. 실제 효과는 Kernel 구현에 달려 있으므로 HBM/GDDR 종류나 표기 대역폭만 보고 성능을 확정하지 않는다.

### 3.4. Precision과 Kernel 지원

FP16, BF16, FP8, INT8, INT4처럼 낮은 Precision은 메모리와 Memory Traffic을 줄이고 지원되는 Tensor Core를 사용할 수 있게 한다. 하지만 다음 세 조건이 모두 맞아야 한다.

1. GPU가 해당 dtype 연산을 지원한다.
2. Framework와 Runtime에 모델 구조용 Kernel이 있다.
3. 실제 Tensor Shape와 Quantization 방식이 Kernel 조건에 맞는다.

지원하지 않는 연산이 더 높은 Precision으로 변환되거나 Dequantization이 자주 발생하면 기대한 성능 향상이 사라질 수 있다.

## 4. GPU 서버의 나머지 구성요소

### 4.1. CPU와 System RAM

CPU는 Tokenization, Data Loading, Request Scheduling, Network 처리와 GPU Kernel 제출을 담당한다. Training에서는 Dataset 변환과 DataLoader Worker가 CPU를 많이 사용할 수 있고, Serving에서는 작은 요청을 높은 빈도로 처리할 때 CPU 병목이 나타날 수 있다.

System RAM은 Dataset Cache, Model Loading, Checkpoint 조립과 CPU Offload 공간으로 사용된다. Sharded Weight를 읽어 GPU에 적재하는 과정에서 순간적으로 Weight 크기보다 많은 RAM이 필요할 수 있으므로 정상 실행 중 사용량만 보고 산정하지 않는다.

### 4.2. Host와 GPU 사이의 연결

일반적인 GPU는 PCIe를 통해 CPU·RAM과 데이터를 주고받는다. GPU가 빠르더라도 매 Step마다 큰 Tensor를 Host로 복사하면 PCIe가 병목이 된다. Pinned Memory와 비동기 전송은 복사와 계산을 겹치는 데 도움이 되지만 메모리 사용과 실행 복잡도가 증가한다.

통합 메모리 또는 CPU-GPU Coherent Interconnect를 제공하는 시스템은 데이터 경로가 다를 수 있다. `통합 메모리`라는 이름만으로 복사 비용이 사라지거나 모든 메모리가 동일한 대역폭을 갖는다고 가정하지 않는다.

### 4.3. Storage와 Model Loading

Model Weight, Dataset와 Checkpoint가 커지면 Storage Capacity뿐 아니라 순차 읽기 처리량, IOPS와 Network Storage 경로가 시작 시간을 결정한다.

```text
Object/Network Storage
→ Local Disk 또는 Cache
→ System RAM
→ VRAM
→ Warm-up과 Kernel 준비
→ 요청 처리 가능
```

GPU가 할당된 뒤 Model Download를 시작하면 GPU 비용을 지불하면서 기다릴 수 있다. Image에 모든 Weight를 포함하면 시작은 단순해질 수 있지만 Image가 지나치게 커지고 모델 교체가 어려워진다. Local Cache, Shared Storage와 사전 배치는 변경 주기와 장애 복구 요구에 맞춰 선택한다.

### 4.4. Network

Network는 API Traffic뿐 아니라 분산 Training의 Gradient, Tensor Parallel 통신, Checkpoint와 Dataset 전송을 처리한다. 단일 GPU 추론에서는 일반 Network로 충분할 수 있지만 Multi-node Training이나 Inference에서는 GPU 간 통신이 Network Latency와 Bandwidth에 직접 영향을 받는다.

NIC 속도만 확인하지 말고 GPU Direct 경로, PCIe Topology, NUMA 배치, Switch Oversubscription과 Collective 통신 성능을 함께 검증한다.

## 5. 다중 GPU와 GPU Cluster

### 5.1. GPU를 여러 개 사용하는 이유

다중 GPU는 두 목적에 사용된다.

- 모델과 실행 상태가 한 GPU의 VRAM에 들어가지 않아 분할한다.
- 더 많은 Batch나 요청을 동시에 처리해 전체 처리량을 높인다.

두 목적은 같은 구성이 아니다. 첫 번째는 GPU 간 통신이 요청 경로에 들어가기 쉽고, 두 번째는 독립 Replica로 분리할 수 있다.

### 5.2. 병렬화 방식

| 방식 | 나누는 대상 | 주된 목적 | 주요 비용 |
| --- | --- | --- | --- |
| Data Parallel | Batch·요청, 모델은 복제 | Training·Serving 처리량 | Gradient 동기화 또는 Weight 중복 |
| Tensor Parallel | Layer 내부 Tensor | 큰 모델 수용, 단일 요청 처리 | Layer마다 빈번한 Collective 통신 |
| Pipeline Parallel | Layer 구간 | 큰 모델 수용 | Stage 간 전송과 Pipeline Bubble |
| Sharded Training | Weight·Gradient·Optimizer State | Training Memory 절감 | All-gather와 Reduce-scatter |
| Expert Parallel | MoE Expert | MoE 모델 분산 | Token Routing과 All-to-all |

Serving Replica를 늘리는 것은 한 요청을 빠르게 만드는 방식이 아니라 동시 요청 처리량을 높이는 방식이다. Tensor Parallel은 Weight를 나누지만 통신이 느리면 단일 GPU보다 Latency가 나빠질 수 있다.

### 5.3. GPU Interconnect와 Topology

동일 서버 안에서도 GPU가 모두 같은 방식으로 연결되는 것은 아니다. GPU 간 경로는 PCIe Host Bridge를 통과할 수도 있고 NVLink와 NVSwitch 같은 전용 Interconnect를 사용할 수도 있다.

```text
GPU ── High-bandwidth Link ── GPU
 │                            │
PCIe                         PCIe
 │                            │
CPU/NUMA Node ── System Link ─CPU/NUMA Node
```

Logical GPU 번호가 물리적으로 가까운 순서를 보장하지 않는다. Tensor Parallel Rank와 NIC를 배치할 때 실제 Topology를 확인해야 한다. GPU 수가 같아도 연결 구조가 다르면 Collective 성능이 크게 달라질 수 있다.

### 5.4. Multi-node Network

서버를 넘어가면 GPU 간 데이터가 NIC와 Switch를 통과한다. NCCL 같은 통신 Library는 All-reduce, All-gather, Reduce-scatter와 All-to-all을 수행하며 가능한 Hardware Topology를 활용한다.

분산 실행에서 확인할 항목은 다음과 같다.

- GPU당 유효 Network Bandwidth와 Latency
- RDMA와 GPUDirect RDMA 지원 경로
- NIC와 GPU의 NUMA·PCIe 근접성
- Switch 계층과 Oversubscription
- Collective별 Payload 크기와 통신 빈도
- 장애 시 전체 Job 재시작 또는 부분 복구 방식

GPU를 두 배로 늘려도 성능이 두 배가 되지는 않는다. 통신과 동기화, 불균형, 작은 Batch와 I/O 병목이 Scaling Efficiency를 낮춘다.

## 6. GPU Software Stack

### 6.1. 계층 구조

NVIDIA CUDA 환경은 대체로 다음 계층으로 실행된다.

```text
Application / Model
Serving Runtime 또는 Training Code
Framework (PyTorch, TensorFlow 등)
Optimized Library와 Kernel (cuBLAS, cuDNN, NCCL 등)
CUDA Runtime
NVIDIA Driver
GPU Hardware
```

- **Driver**는 OS가 GPU를 제어하고 Application의 GPU 접근을 제공한다.
- **CUDA Toolkit**은 Compiler, Runtime, 개발 도구와 Library를 묶은 개발 환경이다.
- **cuBLAS**는 선형대수, **cuDNN**은 Attention·Convolution·Normalization 등 DNN Primitive, **NCCL**은 Multi-GPU Collective 통신을 제공한다.
- **Framework**는 Model 연산을 적절한 Backend Operator와 Kernel로 Dispatch하고 메모리와 자동 미분을 관리한다.
- **Serving Runtime**은 Model Loading, Batching, KV Cache와 API 처리를 관리한다.

PyTorch가 곧 CUDA는 아니다. PyTorch는 상위 Framework이고, NVIDIA GPU에서는 CUDA Backend를 사용한다. AMD GPU의 ROCm처럼 다른 GPU Software Stack도 존재하며 Hardware, OS, Framework와 Operator 지원 범위를 별도로 확인해야 한다.

### 6.2. Host와 Container의 경계

Container는 GPU 자체를 가상화하지 않는다. Host의 GPU Driver와 Device를 NVIDIA Container Toolkit 같은 구성요소가 Container에 노출하고, CUDA Runtime과 Framework Library는 주로 Container Image에 포함한다.

```text
Host:      Kernel + GPU Driver + Physical GPU
                         │
Container: CUDA Runtime Library + Framework + Application
```

따라서 Host에 `nvcc`가 없더라도 미리 빌드된 CUDA Application Container는 실행될 수 있다. 반대로 Host Driver가 Container의 CUDA Application 요구사항을 충족하지 못하면 실행되지 않는다. Custom CUDA Extension을 빌드해야 할 때는 Compiler와 Header가 포함된 개발 Image 또는 Toolkit이 필요하다.

### 6.3. Version Compatibility

버전은 `Framework → 포함된 CUDA Runtime과 Library → 최소 Driver → GPU Architecture` 방향으로 확인한다. 임의의 최신 버전을 각각 설치해서 조합하지 않는다.

`nvidia-smi`에 표시되는 CUDA Version은 Driver가 지원하는 상한을 뜻하며, Host에 설치된 CUDA Toolkit의 `nvcc --version`과 같은 값이 아니다. Container 내부 Framework가 실제로 어떤 CUDA Runtime으로 Build됐는지도 별도로 확인해야 한다.

CUDA에는 Driver의 Backward Compatibility와 같은 Major 계열 내 Minor Version Compatibility가 있지만, 신규 기능이나 PTX JIT처럼 예외가 있다. 실제 Framework와 Runtime의 지원 Matrix 및 CUDA Release Notes를 기준으로 고정한다.

### 6.4. Kernel과 Compile 최적화

Framework의 Eager 실행은 연산마다 Kernel을 제출한다. Kernel Fusion, Graph Compile과 CUDA Graph는 여러 연산 또는 반복 실행의 CPU·Launch Overhead를 줄일 수 있다. 다만 Dynamic Shape, 조건 분기, 메모리 주소 고정 같은 제약 때문에 모든 Workload에 같은 효과를 내지 않는다.

최적화 기능을 켰다는 사실보다 End-to-end 지표가 개선됐는지 확인해야 한다. Compile 시간, 첫 요청 지연, 추가 VRAM, Fallback Operator와 결과 정확도를 함께 측정한다.

## 7. GPU 공유와 격리

### 7.1. 공유 방식 비교

| 방식 | 자원 구분 | 격리 특성 | 적합한 경우 |
| --- | --- | --- | --- |
| 전용 GPU | GPU 전체 | 가장 단순하고 예측 가능 | 큰 모델, 성능 민감, 분산 작업 |
| Time-slicing | 실행 시간을 교대로 사용 | Compute·Memory 성능 격리가 약함 | 간헐적인 개발·추론 작업 |
| CUDA MPS | 여러 CUDA Process를 동시 실행 | 주소 공간은 분리되나 Cache·대역폭 등 공유 | 협력적인 소형 CUDA 작업, MPI 활용 |
| MIG | 지원 GPU를 Compute·Memory 단위로 Hardware Partition | Memory Capacity·대역폭과 장애 격리가 상대적으로 강함 | 독립 Tenant, 예측 가능한 소형 Instance |
| vGPU | Hypervisor와 vGPU Software로 분할 | Profile과 제품 구성에 따라 다름 | VM 기반 공유와 VDI·Compute 혼합 환경 |

같은 `GPU 1개` Resource 표기라도 전용 GPU, Time-slicing과 MIG Instance는 성능과 격리가 다르다. Scheduler가 할당 성공으로 표시해도 실제 VRAM 보장이나 처리량 보장을 의미하지 않을 수 있다.

### 7.2. Time-slicing과 MPS의 주의점

Time-slicing은 여러 Process가 GPU Context를 번갈아 사용하도록 해 유휴 자원을 줄인다. 일반적으로 한 Workload가 다른 Workload의 실행 시간과 Memory Bandwidth에 영향을 줄 수 있으며, 합산 VRAM 사용량도 관리해야 한다.

CUDA MPS는 여러 CUDA Process의 작업을 GPU에 더 효율적으로 공급하기 위한 Client-Server Runtime이다. 제한적인 실행 자원 제어는 가능하지만 MIG와 같은 Hardware Memory Bandwidth·장애 격리를 제공하지 않는다. 신뢰 수준이 다른 Tenant를 단순 MPS만으로 격리했다고 간주하지 않는다.

### 7.3. MIG의 주의점

MIG는 지원되는 NVIDIA GPU에서 SM, Memory Slice, Cache와 Memory Controller 경로를 Instance별로 나눈다. Time-slicing보다 예측 가능한 자원과 격리를 제공하지만 다음 제약이 있다.

- 모든 GPU와 Profile에서 지원되는 기능이 아니다.
- Profile마다 Compute와 VRAM 비율이 고정된다.
- 재구성 시 Workload 중단이나 관리 권한이 필요할 수 있다.
- P2P, NCCL, Monitoring과 일부 기능의 지원 범위가 Driver·GPU 세대에 따라 달라진다.
- 너무 작은 Instance는 Weight가 들어가도 KV Cache와 Runtime Workspace가 부족할 수 있다.

공유 방식은 평균 GPU Utilization이 아니라 Tenant 격리, Tail Latency, VRAM 상한, 장애 영향과 운영 복잡도로 선택한다.

## 8. GPU 시스템 검증 방법

### 8.1. 사양표에서 먼저 확인할 것

1. 모델 Weight, dtype와 Runtime이 GPU Architecture에서 지원되는가
2. Weight, KV Cache, Activation과 Workspace가 VRAM에 들어가는가
3. 목표 단계가 Compute-bound인지 Memory-bound인지
4. CPU, RAM과 Storage가 Loading·전처리를 감당하는가
5. 다중 GPU라면 실제 Interconnect와 NUMA Topology가 적합한가
6. Multi-node라면 Collective 통신에 필요한 Network가 제공되는가
7. Driver, Runtime, Framework와 Kernel 조합이 공식 지원 범위인가

### 8.2. Benchmark에서 측정할 것

Peak 사양 대신 실제 Model, Prompt 분포, Batch와 동시성으로 측정한다.

| 관찰 현상 | 먼저 확인할 항목 |
| --- | --- |
| GPU Utilization이 낮음 | CPU 전처리, 작은 Batch, I/O, 동기화, Unsupported Operator |
| Utilization은 높은데 느림 | Memory Bandwidth, 낮은 Tensor Core 사용률, 비효율 Kernel |
| OOM | Weight 외 KV Cache, Activation, Workspace, Fragmentation |
| GPU 추가 후 Scaling이 낮음 | Interconnect, Collective 시간, Rank 배치, Workload 불균형 |
| 첫 실행만 느림 | Model Loading, Warm-up, Compile, Kernel Autotuning |
| 공유 후 Tail Latency 증가 | Time-slicing, Memory Bandwidth 경쟁, CPU·Network 경쟁 |

Training은 Step Time과 Scaling Efficiency, Serving은 TTFT, Inter-token Latency, Token/sec, Throughput과 Tail Latency를 함께 본다. 평균값만으로 Capacity를 확정하지 않는다.

## 9. 정리

- AI Workload는 큰 Tensor 연산을 반복하므로 GPU의 병렬 연산과 높은 Memory Bandwidth를 활용한다.
- Transformer 전체가 같은 병목을 갖지 않는다. Prefill, Decode, Training과 개별 Operator의 성격을 구분해야 한다.
- VRAM Capacity는 실행 가능 여부를, Compute와 Memory Bandwidth는 주로 실행 속도를 결정한다.
- GPU 성능은 CPU, RAM, Storage, PCIe, Network와 Software Kernel이 준비돼야 실제 처리량으로 이어진다.
- 다중 GPU는 VRAM과 처리량을 늘리지만 통신 비용 때문에 선형으로 확장되지 않는다.
- Container는 Host Driver를 대체하지 않으며 Framework, CUDA Runtime, Driver와 GPU Architecture의 호환성을 함께 관리해야 한다.
- GPU 공유는 활용률뿐 아니라 메모리·성능·장애 격리 수준을 기준으로 선택한다.

## 10. References

- NVIDIA, [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/)
- NVIDIA, [GPU Performance Background User's Guide](https://docs.nvidia.com/deeplearning/performance/dl-performance-gpu-background/index.html)
- NVIDIA, [Matrix Multiplication Background User's Guide](https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html)
- NVIDIA, [cuDNN documentation](https://docs.nvidia.com/deeplearning/cudnn/latest/)
- NVIDIA, [CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/latest/)
- NVIDIA, [NCCL Collective Operations](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/collectives.html)
- NVIDIA, [Multi-Instance GPU User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/)
- NVIDIA, [Multi-Process Service](https://docs.nvidia.com/deploy/mps/)
- NVIDIA, [Container Toolkit Architecture Overview](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/arch-overview.html)
- PyTorch, [Tensors](https://docs.pytorch.org/tutorials/beginner/basics/tensorqs_tutorial.html)
- PyTorch, [CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html)
- PyTorch, [Distributed communication package](https://docs.pytorch.org/docs/stable/distributed.html)
- AMD, [What is ROCm?](https://rocm.docs.amd.com/en/latest/about/what-is-rocm.html)
