# GPU 모델 실행 환경 구성

NVIDIA GPU가 연결된 Linux Host 또는 VM에서 AI 모델을 실행하기 위한 기본 환경을 구성한다. 단일 Host, Container, Kubernetes, GPU Sharing과 Slurm에서 공통으로 확인해야 할 설치 계층과 검증 방법을 다룬다.

## 1. 환경 구성요소

### 1.1. 전체 구성

GPU 모델은 Framework만 설치한다고 실행되지 않는다. Hardware부터 Application까지 각 계층이 호환되어야 한다.

```text
Model / Training·Inference Application
Framework·Serving Runtime
cuDNN·cuBLAS·NCCL 등 GPU Library
CUDA Runtime
NVIDIA Driver
Linux Kernel / OS
GPU Hardware
```

| 계층 | 역할 | 주요 확인 항목 |
| --- | --- | --- |
| GPU Hardware | Tensor 연산과 VRAM 제공 | GPU Architecture, VRAM, Compute Capability |
| NVIDIA Driver | OS와 CUDA Application의 GPU 접근 | GPU·OS·CUDA 호환성, Kernel Module |
| CUDA Toolkit | Compiler, Header, 개발 도구와 Runtime Library | 개발 필요 여부, Driver 호환성 |
| GPU Library | DNN·행렬·통신 연산 최적화 | cuDNN, cuBLAS, NCCL Version |
| Framework | Model 연산과 Tensor 관리 | CUDA 지원 Build, Python Version |
| Application | Model Loading, Training 또는 Serving | Model 형식, dtype, 필요한 GPU 수 |

CUDA는 NVIDIA GPU용 Software Stack이다. AMD GPU는 ROCm, Intel GPU는 해당 Accelerator Stack처럼 다른 구성요소와 지원 Matrix를 사용한다. 이후 예시는 NVIDIA CUDA 환경을 기준으로 한다.

### 1.2. 설치 전에 결정할 항목

설치를 시작하기 전에 다음 항목을 먼저 고정한다.

1. 실행할 Model과 Runtime 또는 Framework
2. Training, Fine-tuning, Inference 중 실행 목적
3. 필요한 VRAM과 GPU 수
4. Framework가 지원하는 CUDA Runtime 계열
5. GPU와 OS를 지원하는 Driver Branch
6. Host 직접 설치 또는 Container 실행 여부
7. 단일 사용자, 공유 Host, Kubernetes 또는 Slurm 여부

Driver와 CUDA부터 임의의 최신 버전으로 설치한 뒤 Framework를 맞추면 의존성 충돌이 생기기 쉽다. 실행할 Framework·Runtime의 공식 설치 조합을 먼저 정하고 필요한 Driver 하한을 역으로 확인한다.

## 2. GPU Host 또는 VM 준비

### 2.1. Hardware와 OS 확인

GPU VM은 생성된 Instance 이름만 믿지 말고 Guest OS에서 실제 Device를 확인한다.

```bash
lspci | grep -i nvidia
uname -r
cat /etc/os-release
```

- `lspci`에 GPU가 없으면 VM에 GPU가 연결되지 않았거나 Passthrough가 실패한 상태다.
- OS와 Kernel이 Driver 지원 범위에 포함되는지 확인한다.
- Secure Boot를 사용하면 Kernel Module 서명이나 등록이 추가로 필요할 수 있다.
- Multi-GPU·NVSwitch 시스템은 Fabric Manager 같은 추가 구성요소가 필요할 수 있다.

Cloud의 Deep Learning Image는 빠르게 시작할 수 있지만 포함된 Driver, CUDA와 Framework Version을 기록한다. Image 교체나 자동 Update로 실행 환경이 바뀌지 않도록 Image ID와 Package Version을 고정한다.

### 2.2. NVIDIA Driver 설치

Driver는 Host OS에 설치한다. 일반적으로 NVIDIA Repository와 배포판 Package Manager를 사용하면 Package 추적, Kernel Update와 제거가 수월하다. `.run` Installer는 배포판 Package Database와 분리되므로 특별한 이유가 있을 때만 사용한다.

설치 과정은 배포판마다 다르지만 순서는 동일하다.

```text
지원 OS·Kernel 확인
→ NVIDIA Package Repository 구성
→ 적합한 Driver Branch 설치
→ 필요 시 재부팅
→ Kernel Module과 GPU 확인
```

Driver 설치 후 다음 명령으로 확인한다.

```bash
nvidia-smi
lsmod | grep nvidia
```

`nvidia-smi`에서 확인할 항목은 다음과 같다.

- Driver Version
- GPU 이름과 UUID
- GPU별 VRAM
- MIG Mode
- 실행 중인 Process

`nvidia-smi`의 `CUDA Version`은 현재 Driver가 지원하는 CUDA 수준을 나타낸다. Host에 설치된 CUDA Toolkit Version과 같다는 뜻이 아니다.

### 2.3. CUDA Toolkit과 CUDA Runtime

CUDA Toolkit에는 `nvcc`, Header, Debugger, Profiler와 CUDA Library가 포함된다. 모든 실행 Host에 전체 Toolkit이 필요한 것은 아니다.

| 상황 | Host CUDA Toolkit |
| --- | --- |
| CUDA Code나 Custom Extension을 Host에서 Compile | 필요 |
| 미리 Build된 Framework Package 실행 | Package가 Runtime Library를 포함하면 불필요할 수 있음 |
| CUDA Runtime이 포함된 Container 실행 | 일반적으로 Host에는 Driver만 필요 |
| `nvcc`, Nsight 등 개발 도구 사용 | 필요 |

Toolkit이 필요한 경우 NVIDIA가 제공하는 배포판 Package 방식으로 설치하고, 특정 Major·Minor Version을 고정한다. 서로 다른 Package Manager 설치와 `.run` 설치를 섞지 않는다.

```bash
nvcc --version
```

이 명령은 설치된 CUDA Compiler Version을 보여준다. `nvidia-smi`의 CUDA 표시와 값이 다를 수 있으며, 그 자체가 오류는 아니다.

### 2.4. cuDNN, cuBLAS와 NCCL

- **cuBLAS**는 GPU 선형대수와 행렬 연산을 제공한다.
- **cuDNN**은 Attention, Convolution, Normalization 등 DNN 연산을 최적화한다.
- **NCCL**은 Multi-GPU·Multi-node Collective 통신에 사용된다.

Framework Wheel이나 Container Image가 필요한 Library를 포함할 수 있으므로 Host에 중복 설치하기 전에 Package 구성을 확인한다. System Library와 Python Environment의 Library가 함께 검색되면 잘못된 `.so`가 Load될 수 있다.

Custom Build가 아니라면 Framework가 공식 배포하는 Package 또는 Container 조합을 우선 사용한다. cuDNN은 CUDA, Driver, GPU와 OS 지원 Matrix를 함께 확인한다.

### 2.5. Version 호환 순서

```text
Model Runtime / Framework Version 결정
→ 해당 Build가 사용하는 CUDA와 GPU Library 확인
→ CUDA가 요구하는 최소 Driver 확인
→ Driver가 GPU와 OS를 지원하는지 확인
```

새 Driver가 이전 CUDA Application을 실행하는 Backward Compatibility와 같은 Major 계열의 Minor Version Compatibility가 제공되지만 예외가 있다. PTX JIT, 새 기능이나 특정 Library 조합은 더 새로운 Driver가 필요할 수 있으므로 CUDA Compatibility 문서와 Framework 지원 Matrix를 기준으로 판단한다.

## 3. Python Framework 구성

### 3.1. 독립된 Python 환경

시스템 Python에 Package를 직접 섞지 않고 `venv` 또는 Conda Environment를 사용한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Python Version은 Framework와 Serving Runtime이 모두 지원하는 범위로 선택한다. Model Code가 사용하는 Transformers, Tokenizer, Quantization Library와 Custom Extension도 함께 고정한다.

```bash
python --version
python -m pip freeze
```

재현 가능한 환경을 위해 최소한 다음 정보를 저장한다.

- OS Image와 Kernel
- Driver Version
- GPU 이름과 UUID
- Python Version
- Framework와 CUDA Build Version
- Model Revision
- 설치 Package Lock 또는 Container Image Digest

### 3.2. PyTorch 설치와 확인

PyTorch 공식 설치 Selector에서 OS, Package Manager와 CUDA 또는 ROCm Build를 선택한다. `pip install torch`를 임의로 실행하기보다 원하는 Accelerator Build가 설치되는지 명령을 확인한다.

설치 후 다음과 같이 검증한다.

```bash
python - <<'PY'
import torch

print("torch:", torch.__version__)
print("built CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("GPU count:", torch.cuda.device_count())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    x = torch.randn(2048, 2048, device="cuda")
    y = x @ x
    torch.cuda.synchronize()
    print("result:", y.shape, y.device)
PY
```

`torch.cuda.is_available()`만 확인하면 GPU가 보인다는 사실만 알 수 있다. 실제 Tensor 연산과 Synchronization까지 성공해야 기본 실행 경로를 검증한 것이다.

### 3.3. TensorFlow 설치와 확인

TensorFlow를 사용하는 경우 공식 GPU 설치 방식과 현재 Python 지원 범위를 확인한다. Linux용 공식 `pip` Package는 필요한 NVIDIA CUDA Library를 Python Dependency로 설치할 수 있으므로 Host에 같은 Library를 다시 수동 배치하지 않는다.

```bash
python -c 'import tensorflow as tf; print(tf.__version__); print(tf.config.list_physical_devices("GPU"))'
```

PyTorch와 TensorFlow를 같은 Environment에 넣으면 CUDA Library 의존성이 충돌할 수 있다. 운영 목적이 다르면 Environment 또는 Container Image를 분리한다.

## 4. Container에서 GPU 사용

### 4.1. 필요한 구성요소

Container는 Host Driver를 포함하거나 대체하지 않는다.

```text
Host
├── Linux Kernel
├── NVIDIA Driver
├── Docker / containerd / CRI-O
└── NVIDIA Container Toolkit
        ↓ GPU Device와 Driver Library 노출
Container
├── CUDA Runtime
├── Framework / Serving Runtime
└── Model Application
```

Host의 `nvidia-smi`가 먼저 정상 동작해야 한다. 그다음 NVIDIA Container Toolkit을 설치하고 사용할 Container Runtime을 구성한다.

### 4.2. Docker Runtime 구성

Package 설치 후 Docker Runtime을 구성하는 기본 명령은 다음과 같다. 실제 Package Repository 등록과 설치 명령은 OS별 공식 문서를 사용한다.

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

공식 CUDA Image 또는 사용하려는 Application Image에서 GPU 노출을 확인한다.

```bash
docker run --rm --gpus all <CUDA_IMAGE> nvidia-smi
```

특정 GPU만 노출할 때는 GPU Index보다 UUID를 사용하면 재부팅이나 장치 열거 순서 변화에 안전하다.

```bash
docker run --rm --gpus '"device=<GPU_UUID>"' <CUDA_IMAGE> nvidia-smi
```

검증 Image Tag는 문서에 고정된 예시를 복사하지 말고 Host Driver와 Application이 지원하는 CUDA Version으로 선택한다.

### 4.3. Model Container 구성 원칙

- CUDA Runtime과 Framework Version을 Image Tag와 Digest로 고정한다.
- Build Tool이 필요 없는 운영 Image에서는 Compiler와 개발 Package를 제외한다.
- Model Weight는 Image 포함, Object Storage Download 또는 Volume Mount 중 하나로 관리한다.
- Model Revision과 Tokenizer를 함께 고정한다.
- Host의 임의 디렉토리와 모든 GPU를 무조건 Mount하지 않는다.
- Container 시작 성공과 Model Ready 상태를 다른 Health Check로 구분한다.

Weight가 크면 Container 시작 후 Download와 VRAM Loading이 오래 걸릴 수 있다. Process가 실행됐다는 이유로 요청을 받지 말고 실제 Model Loading과 Warm-up이 끝난 뒤 Ready 상태로 전환한다.

## 5. Kubernetes GPU Node 구성

### 5.1. Node 구성요소

Kubernetes에서 GPU를 사용하려면 각 GPU Node에 다음 구성요소가 필요하다.

1. GPU Driver
2. Container Runtime
3. NVIDIA Container Toolkit
4. NVIDIA Device Plugin 또는 GPU Operator
5. GPU Label과 Monitoring 구성

Device Plugin이 정상 등록되면 Node의 `Capacity`와 `Allocatable`에 `nvidia.com/gpu` 같은 Extended Resource가 표시된다.

```bash
kubectl describe node <GPU_NODE>
kubectl get pods -A -o wide
```

GPU Operator는 Driver, Container Toolkit, Device Plugin, GPU Feature Discovery와 Monitoring 구성요소의 배포를 자동화할 수 있다. Cloud Image에 Driver가 이미 설치된 경우 Operator가 Driver까지 다시 관리하지 않도록 설치 방식을 하나로 정한다.

### 5.2. GPU 요청 Pod

기본 Device Plugin에서 GPU는 정수형 Extended Resource로 요청한다.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-check
spec:
  restartPolicy: Never
  containers:
    - name: cuda
      image: <CUDA_IMAGE>
      command: ["nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
```

```bash
kubectl apply -f gpu-check.yaml
kubectl logs gpu-check
kubectl describe pod gpu-check
```

Pod가 `Pending`이면 다음을 확인한다.

- Node에 `nvidia.com/gpu`가 광고되는가
- 이미 다른 Pod가 GPU를 할당받았는가
- Node Selector, Affinity와 Taint/Toleration이 맞는가
- 요청한 MIG Profile이나 GPU Resource 이름이 실제 값과 같은가
- Device Plugin과 Runtime Pod가 정상인가

Kubernetes가 GPU를 할당했다는 사실은 Container 내부 Model이 정상 실행되거나 VRAM이 충분하다는 뜻이 아니다.

## 6. GPU Sharing

### 6.1. 공유 방식 비교

| 방식 | 분할 대상 | VRAM·장애 격리 | 특징 |
| --- | --- | --- | --- |
| 전용 GPU | GPU 전체 | 가장 명확함 | 예측 가능한 성능, 낮은 공유 효율 |
| Time-slicing | 실행 시간 | 없음 | 많은 간헐적 작업 공유, 성능 간섭 가능 |
| CUDA MPS | CUDA Process 실행 자원 | 제한적 | 작은 Kernel의 동시 실행과 MPI 활용 |
| MIG | Compute와 Memory Slice | Hardware 수준 제공 | 정해진 Profile, 지원 GPU 제한 |
| vGPU | Hypervisor Profile | 제품·Profile에 따라 다름 | VM 단위 공유, 별도 Software·License 가능 |

GPU Sharing은 VRAM 부족한 Model을 실행시키는 일반적인 해결책이 아니다. 대부분 한 GPU를 여러 작은 Workload가 나눠 쓰기 위한 방식이며, 각 Partition의 VRAM에 Model과 실행 상태가 들어가야 한다.

### 6.2. Time-slicing

Time-slicing은 여러 Process 또는 Pod가 같은 GPU 실행 시간을 번갈아 사용한다. NVIDIA Kubernetes Device Plugin은 하나의 GPU를 여러 Replica Resource처럼 광고할 수 있다.

```yaml
version: v1
sharing:
  timeSlicing:
    renameByDefault: true
    failRequestsGreaterThanOne: true
    resources:
      - name: nvidia.com/gpu
        replicas: 4
```

위 설정은 GPU 성능이나 VRAM을 4등분해 보장하지 않는다. 각 Pod는 같은 물리 GPU의 Memory와 실행 시간을 공유하므로 한 Pod의 OOM, Memory Bandwidth 사용과 긴 Kernel이 다른 Pod에 영향을 줄 수 있다.

개발 Notebook, 간헐적인 소형 추론처럼 동시 Peak가 낮은 환경에 적합하다. 고정 Latency나 보안 격리가 필요한 서로 다른 Tenant에는 신중하게 사용한다.

### 6.3. CUDA MPS

CUDA Multi-Process Service(MPS)는 여러 CUDA Process의 Kernel이 GPU를 더 효율적으로 공유하도록 중개한다. Multi-process MPI Job이나 각 Process가 GPU를 충분히 채우지 못하는 환경에서 활용할 수 있다.

기본 Daemon 동작 확인 예시는 다음과 같다.

```bash
nvidia-cuda-mps-control -d
ps -ef | grep nvidia-cuda-mps
```

종료할 때는 Control Interface를 사용한다.

```bash
echo quit | nvidia-cuda-mps-control
```

MPS 설정은 Driver 세대와 MPS Version에 따라 Memory·SM 제어 기능이 다르다. MPS를 켰다는 사실만으로 Tenant 간 Memory Bandwidth와 장애 격리가 생기지는 않는다. 사용자 권한, Daemon Namespace, Log와 장애 전파 범위를 공식 MPS 문서에서 확인한다.

### 6.4. MIG

Multi-Instance GPU(MIG)는 지원 GPU를 정해진 Compute·Memory Profile로 분할한다. 각 Instance는 별도 CUDA Device처럼 노출할 수 있다.

지원 여부와 현재 상태를 확인한다.

```bash
nvidia-smi -L
nvidia-smi --query-gpu=name,mig.mode.current,mig.mode.pending --format=csv
nvidia-smi mig -lgip
```

구성 흐름은 다음과 같다.

```text
지원 GPU·Driver 확인
→ 실행 중인 GPU Process Drain
→ MIG Mode 활성화
→ GPU Instance Profile 생성
→ 필요 시 Compute Instance 생성
→ Device Plugin·Slurm GRES에 Instance 노출
→ 각 Instance에서 Model 실행 검증
```

MIG 활성화와 재구성 시 GPU Reset 또는 Workload 중단이 필요할 수 있으며 GPU 세대별 동작이 다르다. P2P, NCCL, Profiling과 Monitoring 지원 범위도 Driver와 GPU 세대에 따라 확인한다.

### 6.5. 공유 방식 선택

- Model 하나가 GPU 대부분을 사용하면 전용 GPU가 단순하다.
- 짧고 간헐적인 신뢰 가능한 작업이 많으면 Time-slicing을 검토한다.
- 협력적인 여러 CUDA Process의 동시 실행이 목적이면 MPS를 검토한다.
- VRAM과 장애 격리가 필요한 소형 Workload라면 지원 GPU에서 MIG를 검토한다.
- VM 단위 분할과 Hypervisor 통합이 필요하면 vGPU를 검토한다.

선택 후에는 평균 GPU Utilization만 보지 말고 Workload별 VRAM Peak, 처리량, p95/p99 Latency와 장애 영향을 측정한다.

## 7. Slurm GPU Cluster 구성

### 7.1. 기본 구성요소

Slurm은 GPU Server를 Compute Node로 등록하고 Queue에 제출된 Job에 CPU, RAM과 GPU를 할당한다.

```text
Login / Submit Node
        │ sbatch, srun
        ▼
slurmctld ───── slurmdbd + Accounting DB(선택)
        │
        ├── slurmd: GPU Compute Node 1
        ├── slurmd: GPU Compute Node 2
        └── slurmd: GPU Compute Node N
```

기본 구성에는 Slurm Controller, Compute Node Daemon, 인증을 위한 Munge, 공유 사용자·UID, DNS/시간 동기화와 공통 Storage 설계가 포함된다.

### 7.2. GPU GRES 등록

Slurm은 GPU를 GRES(Generic Resource)로 등록한다. 아래는 구조를 보여주는 예시이며 실제 Node 이름, CPU, RAM, GPU Type과 File 경로로 바꿔야 한다.

`slurm.conf` 예시:

```ini
GresTypes=gpu
SelectType=select/cons_tres

NodeName=gpu-node-01 CPUs=<CPU_COUNT> RealMemory=<MEMORY_MB> \
  Gres=gpu:<GPU_TYPE>:<GPU_COUNT> State=UNKNOWN

PartitionName=gpu Nodes=gpu-node-01 Default=YES State=UP
```

`gres.conf` 예시:

```ini
AutoDetect=nvml
Name=gpu Type=<GPU_TYPE> File=/dev/nvidia[0-<LAST_INDEX>]
```

`AutoDetect=nvml`은 GPU Type, Device File, Core와 Link 정보를 확인하는 데 사용된다. 설정한 GPU 수와 감지된 GPU가 다르면 Node가 Drain될 수 있으므로 오류를 무시하고 강제로 운영하지 않는다.

```bash
slurmd -G
sinfo -N -o '%N %t %G'
scontrol show node gpu-node-01
```

### 7.3. GPU Job 실행

단일 GPU 검증 Job 예시:

```bash
#!/usr/bin/env bash
#SBATCH --job-name=gpu-check
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:10:00

set -euo pipefail

nvidia-smi
python gpu_check.py
```

```bash
sbatch gpu-check.sh
squeue --me
sacct -j <JOB_ID>
```

Job 안에서는 Slurm이 할당한 GPU만 `CUDA_VISIBLE_DEVICES`에 보여야 한다. GPU 수뿐 아니라 CPU Core, RAM과 GPU의 NUMA Topology를 함께 할당하고 `--gpu-bind`, `--cpus-per-gpu`, `--mem-per-gpu` 같은 옵션을 Workload에 맞게 검증한다.

### 7.4. GPU 접근 격리

`CUDA_VISIBLE_DEVICES`는 Application이 볼 GPU를 선택하는 환경 변수다. 보안 경계 자체는 아니므로 Slurm cgroup Plugin으로 할당되지 않은 Device File 접근을 제한한다.

확인할 항목은 다음과 같다.

- cgroup v2와 Slurm cgroup 설정이 OS에서 일치하는가
- Job 밖에서 다른 GPU Device에 접근할 수 없는가
- Container를 사용할 때 Slurm Allocation이 Container Device와 일치하는가
- MIG Device File과 GRES가 올바르게 매핑되는가
- MPS GRES와 전체 GPU GRES가 동시에 잘못 할당되지 않는가

### 7.5. Multi-GPU와 Multi-node Job

PyTorch Distributed나 NCCL Job에는 Node 수, Node당 GPU 수와 Task 수를 일치시킨다.

```text
Slurm Allocation
→ Node List와 GPU GRES 할당
→ Node별 Process/Rank 시작
→ Rank별 GPU Binding
→ NCCL Network Interface와 Topology 확인
→ Training 또는 Inference 실행
```

GPU가 할당돼도 NCCL 통신 경로가 자동으로 최적화되는 것은 아니다. GPU-NIC NUMA 위치, RDMA, Firewall, Interface 이름과 Shared Storage 부하를 별도로 검증한다.

## 8. 문제 확인 순서

### 8.1. 계층별 점검

아래에서 위로 한 단계씩 확인하면 문제 범위를 빠르게 줄일 수 있다.

```text
1. lspci                 → Guest OS에서 GPU Hardware가 보이는가
2. nvidia-smi            → Driver와 GPU가 정상인가
3. Framework GPU Test    → CUDA Library와 Framework가 맞는가
4. Container GPU Test    → Container Runtime이 GPU를 노출하는가
5. Kubernetes/Slurm Test → Scheduler가 올바른 GPU를 할당하는가
6. Model Load            → VRAM과 Model Runtime이 충분한가
```

### 8.2. 증상별 확인 항목

| 증상 | 먼저 확인할 항목 |
| --- | --- |
| `lspci`에 GPU 없음 | VM GPU 연결, Passthrough, Instance Type |
| `nvidia-smi` 실패 | Driver Module, Kernel 호환, Secure Boot, 재부팅 |
| PyTorch CUDA 사용 불가 | CPU 전용 Build, Driver 하한, Python Environment |
| `nvcc`만 없음 | Toolkit 미설치 여부; 실행만 한다면 정상일 수 있음 |
| Container에서 GPU 없음 | NVIDIA Container Toolkit, Runtime 설정, Device 옵션 |
| Kubernetes Pod Pending | Device Plugin, Allocatable GPU, Resource 이름, Node 정책 |
| Slurm Node Drain | `slurmd -G`, `gres.conf`, 실제 GPU 수·Type 불일치 |
| Model Loading OOM | Weight, dtype, KV Cache, Runtime Workspace와 GPU Sharing |
| Multi-GPU Hang | Rank 수, GPU Binding, NCCL Interface, 방화벽과 Topology |

`CUDA out of memory`는 Driver 설치 실패가 아니라 Model과 실행 설정이 할당된 VRAM을 초과한 경우가 대부분이다. 환경을 다시 설치하기 전에 실제 GPU, Process별 VRAM과 Model 설정을 확인한다.

## 9. 정리

- GPU 환경은 Hardware, Driver, CUDA Library, Framework와 Application 계층을 순서대로 검증한다.
- 전체 CUDA Toolkit은 Compile과 개발 도구가 필요할 때 설치하며, 미리 Build된 Package나 Container 실행에는 Host Driver만 필요한 경우가 많다.
- Framework가 사용하는 CUDA Build와 Driver 하한을 기준으로 Version을 맞춘다.
- Container와 Kubernetes는 Host Driver를 대체하지 않는다.
- GPU Sharing은 실행 가능성, 격리와 성능 간섭을 함께 검토한다.
- Slurm에서는 GPU GRES 등록, cgroup Device 격리와 GPU·CPU·NIC Binding을 함께 구성한다.

## 10. References

- NVIDIA, [Driver Installation Guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/latest/)
- NVIDIA, [CUDA Installation Guide for Linux](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/)
- NVIDIA, [CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/latest/)
- NVIDIA, [cuDNN Installation](https://docs.nvidia.com/deeplearning/cudnn/installation/latest/)
- PyTorch, [Start Locally](https://pytorch.org/get-started/locally/)
- TensorFlow, [Install TensorFlow with pip](https://www.tensorflow.org/install/pip)
- NVIDIA, [Installing the NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- Kubernetes, [Schedule GPUs](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- NVIDIA, [GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/)
- NVIDIA, [Time-Slicing GPUs in Kubernetes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
- NVIDIA, [Multi-Instance GPU User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/)
- NVIDIA, [Multi-Process Service](https://docs.nvidia.com/deploy/mps/latest/)
- SchedMD, [Slurm Workload Manager Overview](https://slurm.schedmd.com/overview.html)
- SchedMD, [Generic Resource Scheduling](https://slurm.schedmd.com/gres.html)
- SchedMD, [cgroup v2](https://slurm.schedmd.com/cgroup_v2.html)
