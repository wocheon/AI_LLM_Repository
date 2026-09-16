# GPU Cluster 구성과 GPU 공유

GPU Cluster를 구성하는 방식과 한 GPU를 여러 Workload가 공유하는 방식을 정리한다. 분산 실행 Runtime, Cluster 자원 관리자, Kubernetes Batch 확장 기능과 GPU 분할 기술은 서로 다른 계층이므로 하나의 선택지 목록으로 혼합하지 않는다.

제품별 지원 범위와 API 상태는 2026-09-15 기준이다. GPU 종류, Kubernetes·GKE Version과 기능 상태는 변경될 수 있으므로 실제 구축 시 References의 공식 문서를 다시 확인한다.

## 1. 분류 기준

### 1.1. 두 개의 독립적인 축

구성은 먼저 두 축으로 나눈다.

1. **여러 GPU·Node를 하나의 Cluster로 운영하는 방식**
   - Docker + vLLM + Ray
   - Slurm
   - Kubernetes
   - Kubernetes + Kueue 또는 Volcano
2. **한 물리 GPU를 Workload에 노출하는 방식**
   - Exclusive GPU
   - GPU Time-Sharing
   - NVIDIA MPS
   - NVIDIA MIG

첫 번째 축은 Job이나 Model Process를 어느 Node에서 실행할지 결정한다. 두 번째 축은 선택된 Node 안의 물리 GPU를 하나의 Workload가 전용으로 사용할지, 여러 Workload가 나눠 사용할지 결정한다.

따라서 `Kubernetes + MIG`, `Slurm + MPS`, `Kubernetes + Exclusive GPU`처럼 두 축을 조합할 수 있다. 모든 조합이 제품과 GPU에서 지원되는 것은 아니며, 분산 Workload에는 전용 GPU가 일반적으로 더 예측 가능하다.

### 1.2. 계층 구조

```text
사용자 요청 또는 Batch Job
            │
            ▼
Model Runtime / Distributed Runtime
vLLM, Ray, PyTorch Distributed, NCCL
            │
            ▼
Cluster 자원 관리와 배치
Slurm 또는 Kubernetes
            │
            ├── Kubernetes Batch Admission·Scheduling 확장
            │   Kueue, Volcano 또는 Native Gang Scheduling
            ▼
GPU 노출 방식
Exclusive, Time-Sharing, MPS, MIG
            │
            ▼
Node Hardware
GPU, CPU, RAM, Local Storage, NIC, GPU Interconnect
```

Docker는 실행 환경을 Packaging하고 격리하는 Container Runtime 계층이다. vLLM은 Model Serving Runtime이고 Ray는 분산 Process 배치와 실행을 담당한다. 이 조합은 Slurm이나 Kubernetes가 제공하는 전체 Cluster 자원 정책, Tenant Queue와 Node Lifecycle 관리를 자동으로 대체하지 않는다.

Kueue는 Kubernetes Job이 시작되기 전 Queue, Quota와 Admission을 관리한다. Volcano는 자체 Scheduler와 Batch CRD·Plugin을 사용해 Pod 배치까지 관여한다. 둘을 단순히 같은 기능의 다른 이름으로 보지 않는다.

### 1.3. 다중 GPU Node 구성 방식 비교

| 구성 | 중심 역할 | 대표 Workload | Queue·Quota | Pod·Process 배치 | 적합한 환경 |
| --- | --- | --- | --- | --- | --- |
| Docker + vLLM + Ray | 한 Model Replica의 분산 추론 | Online LLM Serving | 별도 구현 필요 | Ray가 vLLM Worker 배치 | 고정 Node로 빠르게 분산 Serving 구성 |
| Slurm | Linux Cluster 자원 할당과 Job Scheduling | Training, HPC, Batch Inference | Partition, QOS, Account 등 | Slurm이 Job·Task 배치 | Batch 중심 GPU Cluster |
| Kubernetes | Container Orchestration과 Service 운영 | Online Serving, 장기 실행 Service | 기본 ResourceQuota는 있으나 Job Queue는 아님 | 기본 Scheduler가 Pod 단위 배치 | API Service와 Platform 운영 |
| Kubernetes + Kueue | 기존 Kubernetes Job의 Queue·Quota·Admission | Training, Batch Inference, RayJob | ClusterQueue와 LocalQueue | 승인 후 기존 Scheduler가 Pod 배치 | Kubernetes를 유지하면서 Batch Admission 추가 |
| Kubernetes + Volcano | Batch Scheduler와 Job·Queue CRD | MPI, Training, HPC, Batch | Volcano Queue | Volcano Scheduler와 Plugin이 Pod 배치 | Gang·Fair Share·Topology 정책을 Scheduler에 통합 |

Kubernetes 위에서 KubeRay를 사용하면 `Kubernetes + Ray + vLLM` 구성이 된다. 이때 Kubernetes는 Node와 Pod Lifecycle을, Ray는 분산 Actor와 vLLM Worker 배치를, vLLM은 Model 실행과 요청 처리를 담당한다.

### 1.4. 용어 경계

- **Multi-GPU**는 한 Node 또는 여러 Node의 GPU를 함께 사용하는 모든 구성을 뜻할 수 있다.
- **Multi-node**는 Process가 둘 이상의 Server 또는 VM에 걸쳐 실행되는 상태다.
- **Model Parallel**은 하나의 Model Replica를 TP, PP 또는 EP로 분할한다.
- **Data Parallel 또는 Replica 확장**은 Model 사본을 여러 개 두고 Batch나 요청을 나눈다.
- **Gang Scheduling**은 상호 의존하는 여러 Pod·Task가 함께 시작할 수 있을 때 배치하는 정책이다.
- **GPU Sharing**은 물리 GPU 하나를 여러 Process·Container가 나누는 방식이다.

Model Replica가 여러 Node에 걸친다는 사실과 Replica가 여러 개라는 사실을 구분해야 한다. 전자는 한 Node 장애가 전체 Replica에 영향을 주고, 후자는 다른 Replica로 Traffic을 우회할 수 있다.

## 2. Docker + vLLM + Ray 기반 분산 추론

### 2.1. 구성요소의 역할

```text
Client
  │ HTTP
  ▼
vLLM API Server on Ray Head Node
  │
  ├── vLLM Worker / GPU Rank ── Head Node GPU
  ├── vLLM Worker / GPU Rank ── Worker Node 1 GPU
  └── vLLM Worker / GPU Rank ── Worker Node N GPU
              │
              └── NCCL Collective / Pipeline 통신
```

- **Docker**는 모든 Node에서 같은 vLLM, Ray, CUDA Library와 Python Package를 사용하게 한다.
- **Ray Head**는 Cluster Membership과 분산 작업 배치를 조정한다.
- **Ray Worker**는 GPU 자원을 Ray Cluster에 등록하고 vLLM Worker를 실행한다.
- **vLLM**은 Model Weight 배치, KV Cache, Request Scheduling과 API Endpoint를 관리한다.
- **NCCL**은 GPU Rank 사이 Collective 통신을 처리한다.

이 구성의 목적은 여러 GPU Node에 하나의 큰 LLM Replica를 분산하거나, Ray 위에 여러 Replica를 배치하는 것이다. 단순히 Container 수를 늘리는 것만으로 하나의 Model이 분할되지는 않는다.

### 2.2. TP, PP와 Replica 확장

| 방식 | 분할 대상 | 통신 특성 | 일반적인 사용 목적 |
| --- | --- | --- | --- |
| Tensor Parallel, TP | 각 Layer 내부 Tensor | Layer마다 Collective가 자주 발생 | 한 GPU에 Model이 들어가지 않지만 한 Node 안에서 수용 가능 |
| Pipeline Parallel, PP | Layer 구간과 Stage | Stage 경계 Activation 전송, Pipeline Bubble | 한 Node를 넘는 큰 Model 또는 불균등한 GPU 분할 |
| Data Parallel, DP | 요청 또는 Batch, Model은 복제 | Replica 간 요청 분배, MoE 구성에서는 추가 통신 가능 | 동시 처리량과 가용성 확대 |

vLLM 공식 가이드의 일반적인 Multi-node 구성은 `TP 크기 = Node당 GPU 수`, `PP 크기 = Node 수`다. 예를 들어 8 GPU Node 2대로 하나의 Replica를 구성하면 TP 8, PP 2로 시작할 수 있다. TP를 전체 16 GPU로 확장하는 방식도 가능하지만 Node 사이 Collective가 빈번해지므로 Network 성능에 더 민감하다.

```text
Node 0: [TP Rank 0 ... TP Rank 7] = Pipeline Stage 0
                    │ Activation
Node 1: [TP Rank 0 ... TP Rank 7] = Pipeline Stage 1
```

Model이 한 GPU에 들어가는데 처리량만 늘리려는 경우에는 TP·PP로 한 Replica를 크게 만들기보다 독립 Replica를 늘리는 구성이 유리할 수 있다. 이를 판단할 때 TTFT, Inter-token Latency, 전체 Token/sec와 장애 영향을 함께 측정한다.

### 2.3. Node와 Software 준비

모든 Node에서 다음 조건을 일치시킨다.

1. GPU Architecture와 GPU 수
2. NVIDIA Driver와 Container Runtime 호환성
3. vLLM·Ray·CUDA Library가 포함된 동일한 Container Image Digest
4. 동일한 Model Revision, Tokenizer와 Model Mount 경로
5. 충분한 `/dev/shm`, Pinned Memory와 Host RAM
6. Node 사이 양방향 IP 연결, Port와 Firewall 정책
7. NCCL이 사용할 NIC 이름과 RDMA 경로
8. 시간 동기화, DNS 또는 안정적인 Private IP

Model 경로 문자열만 같고 실제 파일이 다르면 Rank별 Weight가 달라질 수 있다. Shared Storage를 사용하거나 각 Node에 동일 Revision을 사전 배치하고 Checksum을 검증한다. GPU 할당 후 Model Download를 시작하면 시작 시간 동안 GPU 비용이 발생하고 일부 Rank만 준비된 채 Timeout이 날 수 있다.

```bash
nvidia-smi -L
nvidia-smi topo -m
docker version
docker run --rm --gpus all \
  --entrypoint nvidia-smi \
  "$VLLM_IMAGE"
```

`VLLM_IMAGE`는 검증한 Version Tag와 가능하면 Digest로 고정한다. 예제의 Image 이름을 운영 환경에서 `latest`처럼 가변 Tag로 사용하지 않는다.

### 2.4. Ray Cluster Container 시작

vLLM Repository의 `examples/ray_serving/run_cluster.sh`는 Node별 Container와 Ray Cluster를 시작하는 보조 Script다. Script를 가져온 Source Revision도 vLLM Image Version과 맞춘다.

Head Node에서 실행하는 구조는 다음과 같다.

```bash
bash run_cluster.sh \
  "$VLLM_IMAGE" \
  <HEAD_NODE_PRIVATE_IP> \
  --head \
  /srv/huggingface \
  -e VLLM_HOST_IP=<HEAD_NODE_PRIVATE_IP>
```

각 Worker Node에서는 Head의 주소와 해당 Worker의 고유 주소를 전달한다.

```bash
bash run_cluster.sh \
  "$VLLM_IMAGE" \
  <HEAD_NODE_PRIVATE_IP> \
  --worker \
  /srv/huggingface \
  -e VLLM_HOST_IP=<WORKER_NODE_PRIVATE_IP>
```

공식 Helper Script 방식은 실행한 Shell이 종료되면 Cluster Container도 종료될 수 있다. Production에서는 systemd, Kubernetes, 별도 Process Supervisor 또는 Infrastructure Automation으로 재시작 정책과 상태 복구를 명시한다.

Ray가 기대한 Node와 GPU를 발견했는지 먼저 확인한다.

```bash
ray status
ray list nodes
```

Ray Dashboard나 Control Port를 Public Network에 직접 노출하지 않는다. vLLM 문서는 Multi-node 내부 Traffic이 암호화되지 않고 신뢰할 수 없는 접근에 안전하지 않다고 명시하므로, Cluster 통신은 접근이 제한된 Private Network에 둔다.

### 2.5. 하나의 Model을 두 Node에 분산

Ray Cluster가 준비된 뒤 Head Container 안에서 하나의 `vllm serve` 명령을 실행한다. 다음은 Node당 8 GPU인 Node 2대를 TP 8, PP 2로 사용하는 구조 예시다.

```bash
vllm serve /models/instruct-model \
  --served-model-name distributed-model \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 2 \
  --distributed-executor-backend ray \
  --max-model-len 8192 \
  --host 0.0.0.0 \
  --port 8000
```

`TP × PP`는 이 Replica에 필요한 GPU 수와 일치해야 한다. 위 예시는 총 16 GPU를 요구한다. `--max-model-len`과 KV Cache 설정은 합산 VRAM이 아니라 각 Rank에 실제로 남은 VRAM을 기준으로 검증한다.

전체 16 GPU를 하나의 TP Group으로 사용할 수도 있다.

```bash
vllm serve /models/instruct-model \
  --tensor-parallel-size 16 \
  --distributed-executor-backend ray
```

두 구성 중 어느 쪽이 빠른지는 Model Architecture, GPU Interconnect, NIC와 통신 Pattern에 따라 달라진다. Cross-node TP는 빠른 Network가 없으면 Latency와 Scaling Efficiency가 급격히 나빠질 수 있다.

### 2.6. vLLM 자체 Multi-node 방식의 위치

현재 vLLM은 Ray 외에 Native Multiprocessing 기반 Multi-node 실행도 제공한다. Head와 Worker에서 `--nnodes`, `--node-rank`, `--master-addr`를 지정하는 방식이다.

```bash
# Head Node
vllm serve /models/instruct-model \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 2 \
  --nnodes 2 \
  --node-rank 0 \
  --master-addr <HEAD_NODE_PRIVATE_IP>

# Worker Node
vllm serve /models/instruct-model \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 2 \
  --nnodes 2 \
  --node-rank 1 \
  --master-addr <HEAD_NODE_PRIVATE_IP> \
  --headless
```

이는 별도 Cluster 구성 방식으로 분류하지 않는다. 같은 `vLLM Multi-node Distributed Inference` 범주 안에서 Ray 대신 선택할 수 있는 실행 Backend다. Ray의 Resource Discovery와 Worker 배치가 필요하지 않은 고정형 구성에는 단순할 수 있지만, Node별 Process Lifecycle과 재시작은 별도로 관리해야 한다.

CLI Option과 기본 Backend는 vLLM Release에 따라 변할 수 있다. 운영 Image에서 다음 명령으로 실제 지원 Option을 확인한다.

```bash
vllm --version
vllm serve --help
```

### 2.7. Network와 성능

Multi-node Model Parallel에서는 HTTP Traffic보다 Rank 사이 통신이 더 큰 병목일 수 있다.

- TP는 빈번한 All-reduce·All-gather 때문에 Latency와 Bandwidth에 민감하다.
- PP는 Stage 사이 Activation을 전송하고 느린 Stage가 전체 Pipeline을 제한한다.
- NIC와 GPU가 다른 NUMA Domain에 있으면 Host 경유 비용이 증가할 수 있다.
- InfiniBand나 RoCE가 있어도 RDMA, GPUDirect RDMA와 NCCL Plugin이 실제 사용되는지 확인해야 한다.
- Switch Oversubscription과 다른 Job의 Network Traffic이 p99 Latency를 악화시킬 수 있다.

Container에서는 Shared Memory와 필요한 Capability를 명시한다. `--privileged`는 편리하지만 Host 공격 표면을 크게 넓히므로 필요한 Device와 `IPC_LOCK` 같은 Capability만 부여하는 구성을 우선한다.

```bash
docker run --rm --gpus all \
  --ipc=host \
  --shm-size=16G \
  -v /dev/shm:/dev/shm \
  -v /srv/models:/models:ro \
  "$VLLM_IMAGE" \
  --model /models/instruct-model \
  --tensor-parallel-size <GPU_COUNT>
```

NCCL Debug Log는 장애 분석 때만 필요한 수준으로 높인다. `TRACE` Log는 양이 많고 성능과 Log Storage에 영향을 줄 수 있다.

```bash
NCCL_DEBUG=INFO vllm serve <MODEL_PATH> <PARALLEL_OPTIONS>
```

### 2.8. 장애와 운영 경계

한 Replica가 2개 Node에 걸치면 Worker Node 한 대의 장애도 전체 Replica 장애가 된다. Online Service는 다음 구조를 검토한다.

```text
Load Balancer
  ├── Distributed Replica A: Node 0 + Node 1
  └── Distributed Replica B: Node 2 + Node 3
```

Replica A와 B가 같은 Node를 공유하면 Node 장애 격리가 사라진다. Ray가 Process를 다시 배치해도 Model Loading과 Collective Group 재구성이 끝날 때까지 요청을 받을 수 없으므로 Readiness와 Traffic Drain이 필요하다.

운영 지표에는 다음을 포함한다.

- Ray Node 수, 사용 가능 GPU와 Worker 상태
- vLLM Ready 상태, Queue Depth와 Running Request 수
- GPU별 VRAM, Utilization, Power와 Error
- Rank별 Model Load 시간과 OOM
- NCCL Timeout, Retry와 Interface 선택
- TTFT, TPOT, Token/sec와 p95·p99 Latency
- Node 또는 Rank 장애 후 복구 시간

## 3. Slurm 기반 GPU Batch·HPC Cluster

### 3.1. 적용 범위

Slurm은 Linux Cluster의 Compute Node를 묶고 GPU, CPU와 RAM을 일정 시간 Job에 할당한다. Pending Job Queue, Priority, Reservation, Accounting과 Parallel Task 실행이 중심이다.

```text
User / CI
   │ sbatch, srun
   ▼
slurmctld ─── Queue, Priority, Allocation
   │
   ├── slurmd on GPU Node 1
   ├── slurmd on GPU Node 2
   └── slurmd on GPU Node N
        │
        └── srun / torchrun / mpirun / Container
```

Training, Batch Inference와 HPC처럼 시작·종료가 명확한 Job에 적합하다. HTTP Service를 장기간 운영할 수도 있지만 Service Discovery, Rolling Update, L7 Routing과 Autoscaling은 별도 구성 책임이다.

### 3.2. GPU 자원 등록과 격리

GPU는 GRES와 TRES로 등록하고 Job이 요청한 Device만 노출한다. 상세한 `slurm.conf`, `gres.conf`와 cgroup 구성은 [GPU 모델 실행 환경 구성](03_gpu_execution_environment.md)의 Slurm 절을 참고한다.

```bash
slurmd -G
sinfo -N -o '%N %t %G'
scontrol show node <GPU_NODE>
```

`AutoDetect=nvml`은 NVIDIA GPU, MIG와 NVLink 정보를 확인하는 데 사용할 수 있다. 최신 Slurm의 `AutoDetect=nvidia`는 NVML Library 없이 NVIDIA GPU를 감지할 수 있지만 MIG와 NVLink를 감지하지 않으므로 동일한 대체 기능으로 간주하지 않는다.

`CUDA_VISIBLE_DEVICES`만으로 다른 Job의 GPU 접근을 막았다고 판단하지 않는다. cgroup Device Constraint를 활성화하고 Container Runtime에 전달되는 Device 목록이 Slurm Allocation과 일치하는지 시험한다.

### 3.3. Multi-node GPU Job

Node당 GPU 4개인 Node 2대를 할당하는 구조 예시는 다음과 같다.

```bash
#!/usr/bin/env bash
#SBATCH --job-name=distributed-gpu
#SBATCH --partition=gpu
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --gpus-per-node=4
#SBATCH --cpus-per-task=8
#SBATCH --mem=0
#SBATCH --time=02:00:00

set -euo pipefail

srun --gpu-bind=closest \
  python distributed_worker.py
```

```bash
sbatch distributed-gpu.sbatch
squeue --me
sacct -j <JOB_ID>
```

`--mem=0`은 Slurm 설정에 따라 Node Memory 전체를 요청하는 의미로 사용된다. 공유 Cluster에서 무조건 복사하지 말고 Partition 정책에 맞는 `--mem` 또는 `--mem-per-gpu` 값을 사용한다.

Process Launcher가 `srun`, `torchrun`, MPI 또는 Application 자체 Launcher인지 하나로 정한다. 여러 Launcher가 동시에 Rank를 생성하면 예상보다 많은 Process가 실행되거나 Rank와 GPU Binding이 어긋날 수 있다.

### 3.4. Queue와 Scheduling 정책

Slurm은 다음 정책을 조합할 수 있다.

- Partition으로 Node 집합과 실행 제한 구분
- Account와 QOS로 사용자·팀별 Priority와 사용 한도 설정
- Reservation으로 특정 기간과 사용자에게 Capacity 배정
- Backfill로 큰 Job 시작 시간을 지연시키지 않는 범위에서 작은 Job 실행
- Topology-aware 배치로 가까운 Node와 Switch 선택
- Preemption으로 우선순위가 높은 Job에 자원 제공

Slurm 문서의 `Gang Scheduling`은 병렬 Job을 번갈아 실행하는 Time-sharing Scheduling을 가리킬 수 있다. Kubernetes 생태계에서 말하는 여러 Pod의 All-or-nothing 배치와 이름은 같지만 동작 문맥이 다르므로 설정 이름만으로 동일 기능이라고 판단하지 않는다.

### 3.5. 운영상 실패 형태

| 증상 | 먼저 확인할 항목 |
| --- | --- |
| Job이 계속 Pending | Partition, QOS, Priority, 요청 GPU Type·수량, Reservation |
| Node가 Drain | `slurmd -G`, GRES 수와 실제 Device 불일치, Health Check Reason |
| 일부 Rank만 실행 | Node·Task·GPU 수, Launcher 중복, Environment 전달 |
| 다른 GPU가 보임 | cgroup Device 설정, Container GPU Mount, `CUDA_VISIBLE_DEVICES` |
| Multi-node Hang | Hostname, Port, Firewall, NIC 선택, RDMA와 NCCL Timeout |
| GPU는 유휴인데 Job 대기 | CPU·RAM 요청, Node Fragmentation, Topology와 Gang 요구조건 |

GPU만 남아 있어도 같은 Node의 CPU, RAM 또는 Local Disk가 부족하면 Job을 배치할 수 없다. Cluster Capacity는 GPU 수 하나가 아니라 동시에 충족해야 하는 Resource Vector로 본다.

## 4. Kubernetes 기반 Container GPU Cluster

### 4.1. 적용 범위

Kubernetes는 GPU Node에 Pod를 배치하고 Deployment, StatefulSet, Job과 Service의 Lifecycle을 관리한다. Online Inference API, 여러 독립 Model Replica와 Platform 공통 운영 기능을 결합하기에 적합하다.

기본 Scheduler는 Pod를 개별적으로 배치한다. 여러 Pod가 동시에 있어야 진행되는 분산 Training이나 MPI Job에는 Queue·Admission과 Gang Scheduling 기능을 추가로 검토한다.

### 4.2. GPU Node와 Extended Resource

GPU Node에는 Driver, Container Runtime, NVIDIA Container Toolkit과 Device Plugin 또는 GPU Operator가 필요하다. Device Plugin이 등록한 GPU는 `nvidia.com/gpu` 같은 Extended Resource로 노출된다.

```bash
kubectl get nodes -o wide
kubectl describe node <GPU_NODE>
kubectl get pods -A -o wide
```

Kubernetes에서 GPU는 일반적으로 `resources.limits`에 정수로 지정한다. `requests`도 지정하면 `limits`와 같은 값이어야 한다.

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

기본 전용 GPU 구성에서는 이 요청 하나가 물리 GPU 하나를 점유한다. Time-slicing이나 MPS를 활성화하면 같은 `nvidia.com/gpu: 1`이 물리 GPU 전체가 아니라 Plugin이 광고한 공유 단위 하나를 뜻할 수 있다. Resource 이름만 보고 실제 격리 수준을 추정하지 않는다.

### 4.3. GPU Model Deployment와 Service

다음 Manifest는 구조를 보여주는 예시다. Image, Model Mount, Probe 경로, CPU·RAM과 GPU Type Label은 실제 Runtime에 맞춘다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: model-server
  template:
    metadata:
      labels:
        app: model-server
    spec:
      nodeSelector:
        accelerator.example.com/model: <GPU_TYPE>
      containers:
        - name: server
          image: <MODEL_SERVER_IMAGE_WITH_VERSION_OR_DIGEST>
          args:
            - --model=/models/instruct-model
            - --host=0.0.0.0
            - --port=8000
          ports:
            - name: http
              containerPort: 8000
          resources:
            requests:
              cpu: "8"
              memory: 32Gi
            limits:
              nvidia.com/gpu: 1
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
          volumeMounts:
            - name: model
              mountPath: /models
              readOnly: true
      volumes:
        - name: model
          persistentVolumeClaim:
            claimName: model-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: model-server
spec:
  selector:
    app: model-server
  ports:
    - name: http
      port: 80
      targetPort: http
```

`Service`는 Ready Pod로 Network Traffic을 전달하지만 Model Queue 길이, KV Cache 상태나 요청별 예상 실행 시간을 알지 못한다. LLM Serving에서는 Runtime-aware Router, Inference Gateway 또는 Application Load Balancer가 필요한지 별도로 검토한다.

### 4.4. 여러 GPU와 여러 Node의 경계

Pod 하나는 하나의 Node에만 배치된다. 따라서 Pod가 `nvidia.com/gpu: 8`을 요청하면 GPU 4개인 Node 두 대에 나눠 배치되지 않고, GPU 8개를 가진 단일 Node가 필요하다.

여러 Node를 하나의 분산 Job이나 Model Replica로 사용하려면 여러 Pod와 분산 Runtime이 필요하다.

```text
Kubernetes
  ├── Head / Coordinator Pod
  ├── Worker Pod on GPU Node A
  └── Worker Pod on GPU Node B
           │
           └── Ray, torch.distributed, MPI 또는 Runtime 자체 Protocol
```

KubeRay의 RayCluster·RayService·RayJob, JobSet, Kubeflow Training Operator 또는 Application 자체 Controller가 이 역할을 할 수 있다. Kubernetes가 `nvidia.com/gpu`를 할당했다는 것만으로 Rank Discovery, Collective 초기화와 Worker 재시작이 구성되지는 않는다.

### 4.5. Scheduling과 Service 운영

GPU Cluster에서는 다음 Kubernetes 기능을 함께 설계한다.

- Node Label, Node Affinity와 Taint/Toleration으로 GPU Type과 Workload 구분
- Pod Affinity·Anti-affinity로 Replica 장애 Domain 분리
- Topology Spread Constraint로 Zone과 Node 분산
- PriorityClass와 Preemption 영향 검토
- PodDisruptionBudget과 Node Upgrade·Drain 정책
- Cluster Autoscaler의 GPU Node 시작 시간과 Scale-down 조건
- Image와 Model Artifact Pre-pull 또는 Local Cache
- Startup, Readiness와 Liveness Probe 분리
- Service, Gateway, TLS와 인증 경계

긴 Model Loading 중 Liveness Probe가 실패하면 Container가 반복 재시작될 수 있다. Startup Probe가 Load 시간을 흡수하고, Readiness는 Model Warm-up까지 끝난 뒤에만 성공하도록 구성한다.

## 5. Kubernetes + Kueue 또는 Volcano

### 5.1. 기본 Kubernetes에 추가하는 이유

기본 Kubernetes Scheduler는 들어온 Pod를 하나씩 배치한다. GPU 8개가 동시에 필요한 분산 Job 두 개가 각각 GPU 4개씩 먼저 점유하면 어느 Job도 진행하지 못하는 Partial Scheduling과 교착 상태가 생길 수 있다.

Batch 확장 계층은 다음 문제를 다룬다.

- 제출된 Job의 대기열
- 팀·Namespace·GPU Type별 Quota
- Job 단위 Admission과 Priority
- 여러 Pod의 동시 시작 조건
- Fair Sharing, Borrowing, Reclaim과 Preemption
- Node·Rack·Zone Topology를 고려한 배치

### 5.2. Kueue의 역할

Kueue는 기존 Kubernetes Scheduler를 교체하지 않고 Job의 시작 여부를 제어하는 Admission Controller다.

```text
Kubernetes Job / RayJob / Training Job
                │
                ▼
           LocalQueue
                │
                ▼
ClusterQueue ── Quota, Flavor, Priority, Fair Sharing
                │ Admission
                ▼
          Job Unsuspend
                │
                ▼
       Kubernetes Scheduler가 Pod 배치
```

- **ResourceFlavor**는 GPU Type, 구매 방식 또는 Node 특성과 연결할 자원 Flavor를 표현한다.
- **ClusterQueue**는 Cluster 범위 Quota와 Fair Sharing 정책을 관리한다.
- **LocalQueue**는 Namespace의 사용자가 Job을 제출하는 Queue다.
- **Workload**는 Kueue가 Admission을 판단하는 Job 단위 객체다.
- **Cohort**는 여러 ClusterQueue가 사용하지 않는 Quota를 빌리고 빌려줄 수 있게 묶는다.

Kueue의 Quota Reservation은 Pod Scheduling과 다르다. Kueue가 Workload를 승인해도 Node Fragmentation, Taint, Affinity나 실제 Cloud Capacity 때문에 Pod가 Pending일 수 있다.

### 5.3. Kueue GPU Queue 예시

다음은 GPU 8개에 대한 단순 Quota 구조 예시다. API Version과 Field는 설치한 Kueue Release의 CRD를 기준으로 확인한다.

```yaml
apiVersion: kueue.x-k8s.io/v1beta2
kind: ResourceFlavor
metadata:
  name: gpu-flavor
spec:
  nodeLabels:
    accelerator.example.com/model: <GPU_TYPE>
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: ClusterQueue
metadata:
  name: gpu-cluster-queue
spec:
  namespaceSelector: {}
  resourceGroups:
    - coveredResources:
        - cpu
        - memory
        - nvidia.com/gpu
      flavors:
        - name: gpu-flavor
          resources:
            - name: cpu
              nominalQuota: 64
            - name: memory
              nominalQuota: 256Gi
            - name: nvidia.com/gpu
              nominalQuota: 8
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: LocalQueue
metadata:
  name: team-gpu-queue
  namespace: team-a
spec:
  clusterQueue: gpu-cluster-queue
```

사용자는 Job에 LocalQueue Label을 지정한다. Kueue Webhook이 지원되는 Job을 관리하며, 설치 설정에 따라 Job의 `suspend` 상태를 제어한다.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: gpu-batch
  namespace: team-a
  labels:
    kueue.x-k8s.io/queue-name: team-gpu-queue
spec:
  parallelism: 4
  completions: 4
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: worker
          image: <GPU_BATCH_IMAGE_WITH_VERSION_OR_DIGEST>
          resources:
            requests:
              cpu: "8"
              memory: 24Gi
            limits:
              nvidia.com/gpu: 1
```

상태는 Job과 Workload를 함께 본다.

```bash
kubectl get localqueues -n team-a
kubectl get clusterqueues
kubectl get workloads -n team-a
kubectl describe workload -n team-a <WORKLOAD_NAME>
kubectl get pods -n team-a
```

### 5.4. Kueue와 All-or-nothing 배치

Kueue는 기본적으로 Workload의 모든 PodSet에 필요한 합산 Quota가 있을 때 승인한다. 하지만 합산 Quota만으로 실제 Node 배치를 보장하지는 않는다.

예를 들어 Cluster 전체에 GPU 8개가 남아 있어도 4 GPU Node 두 대에 나뉘어 있다면 GPU 8개를 요청하는 단일 Pod는 실행할 수 없다. 다음 기능을 Workload 특성에 맞게 조합한다.

- **Topology Aware Scheduling, TAS**: Node·Rack·Block 같은 Topology와 실제 Placement 가능성을 Admission에 반영한다.
- **waitForPodsReady**: 승인 후 정해진 시간 안에 Pod가 Ready가 되지 않으면 Workload를 Evict하고 Quota를 반환한다.
- **ProvisioningRequest AdmissionCheck**: Autoscaler나 Capacity Provisioner가 자원을 준비할 때까지 Admission을 지연한다.
- **Partial Admission 비활성화**: 크기를 줄여 실행하면 안 되는 Job이 일부만 승인되지 않게 한다.

`waitForPodsReady`는 Partial Scheduling을 사전에 완전히 막는 Scheduler Transaction이 아니라 Timeout 기반 복구 장치다. 엄격한 Gang Scheduling이 필요하면 TAS, 지원되는 Workload Integration과 실제 Scheduler 동작을 함께 시험한다.

### 5.5. Volcano의 역할

Volcano는 Kubernetes용 Batch System으로 자체 Scheduler, Controller와 CRD를 제공한다.

```text
VolcanoJob 또는 지원되는 Pod Group
             │
             ▼
Queue ── PodGroup(minMember/minResources)
             │
             ▼
Volcano Scheduler
enqueue → allocate → backfill
             │
             ▼
GPU Node에 Pod 배치
```

- **Queue**는 PodGroup 집합과 Resource 분배 정책을 표현한다.
- **PodGroup**은 연관된 Pod와 최소 실행 수 `minMember`를 정의한다.
- **VolcanoJob**은 여러 Task, Lifecycle Policy, Queue와 최소 가용 Task 수를 표현한다.
- **Scheduler Plugin**은 Gang, Priority, DRF, Proportion, Binpack과 Node Order 같은 정책을 조합한다.

Volcano는 Pod 배치 Scheduler까지 담당하므로 Scheduler Profile과 Plugin 순서가 결과에 직접 영향을 준다. 설정에 `schedulerName: volcano`를 빠뜨리거나 일부 Pod만 기본 Scheduler로 보내면 의도한 Gang 정책이 깨질 수 있다.

### 5.6. Volcano GPU Job 예시

다음 예시는 GPU Worker 4개가 함께 실행 가능할 때 시작하는 구조다.

```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: distributed-gpu-job
spec:
  schedulerName: volcano
  queue: gpu-queue
  minAvailable: 4
  policies:
    - event: PodEvicted
      action: RestartJob
  tasks:
    - name: worker
      replicas: 4
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: worker
              image: <GPU_BATCH_IMAGE_WITH_VERSION_OR_DIGEST>
              resources:
                requests:
                  cpu: "8"
                  memory: 24Gi
                  nvidia.com/gpu: "1"
                limits:
                  nvidia.com/gpu: "1"
```

```bash
kubectl get vcjob distributed-gpu-job -o yaml
kubectl get podgroups
kubectl get queues
kubectl get pods -l volcano.sh/job-name=distributed-gpu-job -o wide
```

`minAvailable`은 Application이 실제로 필요한 Role 구성과 맞아야 한다. Parameter Server 1개와 Worker 4개가 모두 필요하면 단순히 4로 두지 않고 전체 최소 구성과 Task별 장애 정책을 검토한다.

### 5.7. Kueue와 Volcano 선택

| 항목 | Kueue | Volcano |
| --- | --- | --- |
| 기본 위치 | Job Admission과 Queue 관리 | Batch Scheduler와 Job 관리 |
| 기본 Scheduler | 기존 Kubernetes Scheduler 사용 | Volcano Scheduler 사용 |
| 기존 Job 통합 | 지원 Integration의 suspend·unsuspend 제어 | VolcanoJob 또는 PodGroup·Scheduler 지정 |
| Quota 단위 | ResourceFlavor, ClusterQueue, LocalQueue | Queue의 Capability, Guarantee, Weight 등 |
| Gang 접근 | Quota Admission + TAS + Ready 확인 등 | Gang Plugin과 PodGroup `minMember` |
| 운영 영향 | Scheduler 교체 없이 Controller·Webhook 추가 | Scheduler·Controller·CRD와 Plugin 정책 운영 |
| 적합한 경우 | 기존 Kubernetes Platform에 Queue를 추가 | HPC·AI Batch Scheduling을 한 체계로 구성 |

두 제품은 기능이 일부 겹치지만 내부 책임이 다르다. 같은 Workload를 Kueue와 Volcano가 동시에 제어하는 구성은 Admission, Suspension, Queue와 Preemption 정책의 소유권을 먼저 정의하지 않으면 분석하기 어렵다. 특별한 통합 요구가 없다면 한 Workload의 Queue·Gang 정책 소유자를 하나로 정한다.

### 5.8. Kubernetes Native Gang Scheduling 상태

Kubernetes 1.37에서는 Workload API와 PodGroup을 사용하는 Native Gang Scheduling이 Beta로 승격됐다. 다만 `GenericWorkload` Feature Gate는 기본 비활성화 상태다. Cluster Version과 Distribution이 지원하고 Feature Gate를 켠 경우에만 사용할 수 있다.

Native 기능은 기본 Scheduler가 Pod를 그룹 단위로 인식하게 하지만 Kueue의 Tenant Queue·Quota·Borrowing 전체 또는 Volcano의 Batch Job·Plugin 체계를 자동으로 대체하지 않는다. 다음 질문으로 도입 범위를 정한다.

1. 필요한 것이 All-or-nothing Pod 배치뿐인가
2. 팀별 Queue, Quota와 Fair Sharing도 필요한가
3. Custom Batch Job Lifecycle과 Scheduler Plugin이 필요한가
4. Managed Kubernetes가 Feature Gate와 API를 지원하는가

API가 Beta여도 기본 비활성화이며 Provider 지원 시점은 다를 수 있다. Production 도입 전 Upgrade, Rollback, Preemption과 기존 Kueue·Volcano 객체의 상호작용을 별도 Cluster에서 검증한다.

## 6. 단일 GPU 할당과 공유 방식

### 6.1. 비교 기준

| 방식 | 실행 방식 | Compute 분리 | VRAM 분리 | 장애·보안 격리 | 대표 용도 |
| --- | --- | --- | --- | --- | --- |
| Exclusive GPU | 한 Workload에 전체 GPU 할당 | 전용 | 전용 | 가장 단순함 | LLM, 분산 Job, Latency 민감 Serving |
| GPU Time-Sharing | 여러 Context를 빠르게 교대 | 보장된 Slice 없음 | Hard Limit 없음 | 약함 | 간헐적 Notebook, 개발, Bursty Inference |
| NVIDIA MPS | 여러 CUDA Process Kernel 동시 실행 | Active Thread 비율 제어 가능 | Pinned Device Memory 제한 가능 | 제한적 | 협력적인 소형 CUDA·MPI Process |
| NVIDIA MIG | GPU를 Hardware Instance로 분할 | Profile별 전용 Slice | Profile별 전용 Slice | 상대적으로 강함 | 독립적인 소형 Inference, 예측 가능한 QoS |

공유는 GPU 총 VRAM을 늘리지 않는다. 작은 Model 여러 개가 같은 GPU를 효율적으로 사용하는 방법이다. 단일 Partition이나 공유 환경에 Model Weight, KV Cache, Activation과 Runtime Workspace가 들어가야 한다.

### 6.2. Exclusive GPU

기본 Kubernetes Device Plugin이나 Slurm GRES에서 공유 기능을 켜지 않으면 GPU 하나를 Workload 하나에 전용 할당하는 구성이 일반적이다.

장점은 다음과 같다.

- GPU Memory Capacity와 실행 성능을 이해하기 쉽다.
- 다른 Workload의 Kernel과 Memory Bandwidth 간섭이 없다.
- OOM과 GPU Reset의 영향 범위가 명확하다.
- NCCL, Profiling과 Multi-GPU 기능의 제약이 가장 적다.

GPU Utilization이 낮은 간헐적 Workload에는 비용 낭비가 생길 수 있다. 하지만 평균 Utilization을 높이기 위해 공유했다가 p99 Latency와 장애 복구가 악화되면 전체 Capacity가 더 필요할 수 있다.

### 6.3. GPU Time-Sharing

Time-Sharing은 여러 Process나 Container가 같은 물리 GPU Context를 교대로 실행하게 한다. 각 Workload는 실행 차례가 왔을 때 GPU를 사용하지만 Compute 비율이나 VRAM을 Hardware Partition처럼 고정해서 받지 않는다.

적합한 Workload는 다음과 같다.

- GPU 사용 사이에 긴 Idle 구간이 있는 개발 Notebook
- 짧고 간헐적인 Inference 또는 Test
- 같은 Trust Boundary에 있고 성능 간섭을 허용할 수 있는 작업

주의할 점은 다음과 같다.

- 광고된 공유 Resource 수는 물리 GPU 수나 보장된 Compute 배수가 아니다.
- 한 Workload의 VRAM 과다 사용으로 다른 Workload가 OOM 영향을 받을 수 있다.
- 동시 Peak가 겹치면 Throughput과 Tail Latency가 변동한다.
- GPU Reset과 Hardware Error의 영향은 같은 물리 GPU를 공유하는 Workload에 전파될 수 있다.

### 6.4. NVIDIA MPS

MPS는 여러 CUDA Process의 작업을 하나의 GPU에서 동시에 실행할 수 있게 하는 Client-Server Runtime이다. 작은 Kernel을 사용하는 협력적인 Process나 MPI Rank가 GPU를 충분히 채우지 못할 때 처리량을 높일 수 있다.

MPS는 Time-Sharing과 달리 여러 Process Kernel의 동시 실행을 목표로 한다. 그러나 MIG와 같은 독립 Hardware Partition은 아니다.

- Active Thread Percentage로 각 Client의 실행 자원을 제한할 수 있다.
- Pinned Device Memory Limit로 Client Memory 사용을 제한할 수 있다.
- Memory Bandwidth, Encoder·Decoder와 일부 GPU Engine은 같은 방식으로 분할되지 않는다.
- Memory Protection과 Error Containment에는 제약이 있다.
- GKE 구현은 Pod에서 `hostIPC: true`를 요구하므로 보안 영향을 검토해야 한다.

서로 신뢰하지 않는 Tenant를 MPS만으로 격리하지 않는다. MPS Daemon 장애, Client 종료와 Fatal GPU Error가 다른 Client에 미치는 영향을 사용 Driver와 GPU 세대에서 시험한다.

### 6.5. NVIDIA MIG

MIG는 지원 GPU를 정해진 GPU Instance Profile로 분할한다. Instance마다 Compute, Memory Capacity, Cache와 Memory Bandwidth 경로가 분리되며 CUDA Application에는 별도 GPU Device처럼 보인다.

```text
Physical GPU
  ├── MIG Instance A: Compute Slice + VRAM Slice
  ├── MIG Instance B: Compute Slice + VRAM Slice
  └── MIG Instance C: Compute Slice + VRAM Slice
```

MIG는 Time-Sharing이나 MPS보다 처리량과 Latency를 예측하기 쉽다. 대신 Profile 크기가 고정되고 모든 GPU가 MIG를 지원하지 않는다. 재구성에는 Workload Drain과 GPU Reset 또는 Node Lifecycle 작업이 필요할 수 있다.

다음 호환성을 확인한다.

- GPU Model과 Architecture의 MIG 지원 여부
- 필요한 VRAM과 Compute에 맞는 Profile 존재 여부
- Driver, Device Plugin과 Kubernetes·Slurm 노출 방식
- NCCL, P2P, GPUDirect, Profiling과 Monitoring 지원 범위
- Instance 재구성 시 기존 Workload 중단 범위

MIG Instance 안에서 다시 Time-Sharing이나 MPS를 조합할 수 있는 Platform도 있다. 격리 경계는 MIG Instance 사이에 적용되며, 같은 Instance를 다시 공유하는 Workload 사이에는 선택한 Software Sharing의 제약이 적용된다.

## 7. GKE에서 GPU 공유 구성

### 7.1. 지원 범위

2026-09-15 기준 GKE의 주요 지원 범위는 다음과 같다.

| 방식 | GKE Mode | GPU 범위 | T4 | L4 | 핵심 제약 |
| --- | --- | --- | --- | --- | --- |
| Exclusive GPU | Autopilot·Standard | GKE Mode별 지원 GPU | 지원 | 지원 | Container당 정수 GPU 요청 |
| GPU Time-Sharing | Autopilot·Standard | 모든 NVIDIA GPU Model, 일부 Fractional G4 제외 | 지원 | 지원 | VRAM Hard Limit 없음, 동일 Trust Boundary 권장 |
| NVIDIA MPS | Standard | 모든 NVIDIA GPU Type, 일부 Fractional G4 제외 | 지원 | 지원 | `hostIPC: true`, Memory·Error 격리 제한 |
| NVIDIA MIG | Autopilot·Standard | GB200, B200, H200, H100, A100 80GB·40GB, RTX PRO 6000 | 미지원 | 미지원 | Profile 고정, GPU별 GKE Version 조건 |

T4와 L4는 Time-Sharing과 MPS에서 사용할 수 있지만 그 두 GPU에만 한정된 기능은 아니다. 반대로 현재 GKE MIG 지원 목록에는 T4와 L4가 없다. GPU 전체 제품군과 최소 GKE Patch Version은 자주 바뀌므로 Cluster 생성 직전에 공식 지원 표를 확인한다.

### 7.2. GKE GPU Time-Sharing Node Pool

Standard Cluster에서는 공유 전략과 물리 GPU당 최대 Client 수를 Node Pool에 설정한다.

```bash
gcloud container node-pools create <NODE_POOL_NAME> \
  --cluster=<CLUSTER_NAME> \
  --location=<CONTROL_PLANE_LOCATION> \
  --machine-type=<MACHINE_TYPE> \
  --accelerator=type=<GPU_TYPE>,count=1,gpu-sharing-strategy=time-sharing,max-shared-clients-per-gpu=4,gpu-driver-version=<DRIVER_VERSION>
```

위 설정은 물리 GPU 하나를 4등분한 성능과 VRAM을 보장하지 않는다. Scheduler에 네 개의 공유 가능 단위를 광고하는 Admission Capacity 설정에 가깝다.

Workload는 공유 전략 Label과 GPU 한 단위를 요청한다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: timeshared-inference
spec:
  replicas: 4
  selector:
    matchLabels:
      app: timeshared-inference
  template:
    metadata:
      labels:
        app: timeshared-inference
    spec:
      nodeSelector:
        cloud.google.com/gke-gpu-sharing-strategy: time-sharing
        cloud.google.com/gke-max-shared-clients-per-gpu: "4"
      containers:
        - name: inference
          image: <INFERENCE_IMAGE_WITH_VERSION_OR_DIGEST>
          resources:
            limits:
              nvidia.com/gpu: 1
```

`replicas: 4`가 반드시 같은 물리 GPU에 모두 배치된다는 보장은 Node 수와 현재 사용량에 따라 달라진다. 실제 Pod의 Node와 Container에서 보이는 GPU UUID를 확인한다.

```bash
kubectl get pods -l app=timeshared-inference -o wide
kubectl exec <POD_NAME> -- nvidia-smi -L
```

### 7.3. GKE NVIDIA MPS Node Pool

MPS는 GKE Standard에서 구성한다.

```bash
gcloud container node-pools create <NODE_POOL_NAME> \
  --cluster=<CLUSTER_NAME> \
  --location=<CONTROL_PLANE_LOCATION> \
  --machine-type=<MACHINE_TYPE> \
  --accelerator=type=<GPU_TYPE>,count=1,gpu-sharing-strategy=mps,max-shared-clients-per-gpu=4,gpu-driver-version=<DRIVER_VERSION>
```

Pod는 MPS Node를 선택하고 MPS Control Daemon과 IPC 통신하기 위해 `hostIPC: true`를 사용한다.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mps-batch
spec:
  parallelism: 4
  completions: 4
  template:
    spec:
      hostIPC: true
      restartPolicy: Never
      nodeSelector:
        cloud.google.com/gke-gpu-sharing-strategy: mps
        cloud.google.com/gke-max-shared-clients-per-gpu: "4"
      containers:
        - name: cuda-worker
          image: <CUDA_WORKER_IMAGE_WITH_VERSION_OR_DIGEST>
          resources:
            limits:
              nvidia.com/gpu: 1
```

GKE는 `max-shared-clients-per-gpu`를 기준으로 `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE`와 `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT`를 주입할 수 있다. 이 제한은 Memory Bandwidth와 모든 GPU Engine을 같은 비율로 격리하지 않는다.

`hostIPC: true`는 Container가 Host IPC Namespace를 공유하게 하므로 Pod Security 정책과 Tenant Trust Boundary를 검토한다. MPS Node에는 서로 신뢰하는 Workload만 배치하는 별도 Node Pool이 관리하기 쉽다.

### 7.4. GKE MIG Node Pool

다음은 A100 40GB 하나를 `1g.5gb` Profile로 나누는 Standard Node Pool 구조 예시다.

```bash
gcloud container node-pools create <NODE_POOL_NAME> \
  --cluster=<CLUSTER_NAME> \
  --location=<CONTROL_PLANE_LOCATION> \
  --machine-type=a2-highgpu-1g \
  --accelerator=type=nvidia-tesla-a100,count=1,gpu-partition-size=1g.5gb,gpu-driver-version=<DRIVER_VERSION>
```

Pod는 필요한 Partition 크기를 선택하고 GPU 하나를 요청한다. 여기서 `nvidia.com/gpu: 1`은 물리 GPU 전체가 아니라 선택된 MIG Instance 하나다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mig-inference
spec:
  replicas: 7
  selector:
    matchLabels:
      app: mig-inference
  template:
    metadata:
      labels:
        app: mig-inference
    spec:
      nodeSelector:
        cloud.google.com/gke-gpu-partition-size: 1g.5gb
      containers:
        - name: inference
          image: <INFERENCE_IMAGE_WITH_VERSION_OR_DIGEST>
          resources:
            limits:
              nvidia.com/gpu: 1
```

Profile 이름은 GPU 세대와 VRAM에 따라 다르다. `1g.5gb`를 H100, H200 또는 B200에 그대로 사용하지 않는다. GKE 공식 Partition Table과 실제 Node Label을 확인한다.

```bash
kubectl get nodes --show-labels
kubectl describe node <MIG_NODE>
kubectl exec <POD_NAME> -- nvidia-smi -L
```

### 7.5. 공유 전략별 Resource 의미

같은 Manifest 조각도 Node Pool 설정에 따라 의미가 달라질 수 있다.

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

```text
Exclusive Node → 물리 GPU 1개
Time-Sharing Node → 공유 Client Slot 1개
MPS Node → MPS Sharing Unit 1개
MIG Node → MIG Instance 1개
```

Workload에 Sharing Strategy, GPU Type, MIG Profile과 최대 Client 수 Label을 함께 지정하면 의도하지 않은 Node Pool로 배치되는 위험을 줄일 수 있다. Label 값이 Provider나 설치 방식에 따라 다르므로 실제 Node에서 확인한 값을 사용한다.

### 7.6. Monitoring과 Capacity 판단

GKE의 Time-Sharing·MPS 기본 GPU Metric은 Node 단위로 제공되는 항목이 있으므로 Container별 사용량을 항상 정확히 분리할 수 있다고 가정하지 않는다. DCGM Exporter나 Application Metric을 추가할 때도 Driver·Sharing 방식별 지원 범위를 확인한다.

공유 비율은 다음 순서로 결정한다.

1. Workload 하나의 Peak VRAM과 정상 실행 시 여유분 측정
2. 단독 실행 TTFT, TPOT, Throughput과 GPU Utilization 측정
3. 동일 GPU에 2개 Workload를 배치해 동시 Peak 시험
4. 3개 이상으로 늘리며 p95·p99 Latency와 OOM 관찰
5. Workload 실패, 강제 종료와 GPU Error 영향 시험
6. 허용 SLO를 만족하는 최대 공유 수보다 낮게 운영값 설정

`max-shared-clients-per-gpu=48`처럼 제품이 허용하는 상한은 권장 운영값이 아니다. Model 크기와 Latency SLO를 기준으로 실제 공유 수를 정한다.

## 8. 구성 선택 기준

### 8.1. Cluster 구성 선택

| 요구사항 | 우선 검토할 구성 | 이유 |
| --- | --- | --- |
| 고정된 소수 Node에 하나의 큰 LLM Serving | Docker + vLLM + Ray 또는 vLLM Native Multi-node | 분산 Runtime 구성이 직접적임 |
| 여러 팀의 Training·HPC Batch Job | Slurm | Queue, Allocation, Accounting과 Parallel Job 기능이 중심임 |
| 여러 Model API와 일반 Service를 함께 운영 | Kubernetes | Deployment, Service와 Platform 운영 기능 활용 |
| Kubernetes에서 팀별 GPU Queue·Quota 필요 | Kubernetes + Kueue | 기존 Scheduler를 유지하며 Admission 추가 |
| Kubernetes에서 Gang·Batch Scheduler Plugin 필요 | Kubernetes + Volcano | PodGroup과 Batch Scheduler 정책 통합 |
| Kubernetes 1.37+에서 단순 Gang 기능만 필요 | Native Gang Scheduling 검토 | 별도 Scheduler 없이 기본 기능 활용 가능, Feature Gate와 Provider 지원 확인 필요 |

하나의 Cluster가 Online Serving과 대규모 Batch Training을 동시에 처리하면 우선순위와 Preemption이 Service SLO에 영향을 줄 수 있다. Node Pool, Partition 또는 Cluster를 분리할지 비용과 장애 Domain을 함께 검토한다.

### 8.2. GPU 공유 방식 선택

```text
Model과 실행 상태가 한 GPU에 들어가는가?
  ├── 아니오 → GPU 공유가 아니라 Quantization, TP·PP 또는 더 큰 GPU 검토
  └── 예
       │
       ├── 일정한 Latency 또는 Multi-GPU 통신이 중요한가?
       │    └── 예 → Exclusive GPU 우선
       │
       ├── Hardware 수준 VRAM·Compute 분리가 필요한가?
       │    └── 예 → 지원 GPU에서 MIG
       │
       ├── 협력적인 CUDA Process를 동시에 실행하려는가?
       │    └── 예 → MPS
       │
       └── 간헐적인 신뢰 가능한 Workload의 유휴 시간을 줄이려는가?
            └── 예 → Time-Sharing
```

공유 방식은 평균 GPU Utilization 하나로 결정하지 않는다. 최소한 다음 항목을 비교한다.

- Workload별 Peak VRAM과 OOM 영향
- p50뿐 아니라 p95·p99 Latency
- 단독 대비 동시 실행 Throughput
- 서로 다른 Tenant의 Trust Boundary
- GPU Error와 Reset의 장애 전파
- Monitoring과 Chargeback 가능성
- Node Pool Fragmentation과 Autoscaling
- 지원 GPU, Driver와 Platform Version

### 8.3. 조합 예시

| 구성 | GPU 노출 | 적합한 예 | 주의점 |
| --- | --- | --- | --- |
| vLLM + Ray Multi-node | Exclusive | 하나의 초대형 LLM Replica | 한 Node 장애가 전체 Replica에 영향 |
| Slurm | Exclusive | Multi-node Training | Queue 대기와 Topology 배치 |
| Slurm | MIG | 작은 독립 Batch Job | GRES Profile과 Accounting 지원 확인 |
| Kubernetes | Exclusive | Latency 민감 Model API | 낮은 평균 Utilization 가능 |
| Kubernetes + Kueue | Exclusive | 팀별 분산 Training Queue | Admission과 실제 Placement 차이 |
| Kubernetes + Volcano | Exclusive | MPI·Gang Training | Scheduler Plugin과 Queue 정책 운영 |
| GKE | Time-Sharing | 개발 Notebook과 간헐적 Inference | VRAM·Latency 간섭 |
| GKE Standard | MPS | 작은 CUDA Batch Process | `hostIPC`, 제한적인 격리 |
| GKE | MIG | 여러 소형 Inference Replica | T4·L4 미지원, Profile 고정 |

분산 TP·PP Worker를 Time-Sharing GPU에 배치하면 한 공유 Workload의 지연이 Collective Barrier를 통해 전체 Replica 지연으로 확대될 수 있다. 성능과 장애 분석이 중요한 분산 Job은 Exclusive GPU에서 먼저 검증한다.

### 8.4. 피해야 할 혼동

- Docker Compose로 여러 Container를 띄웠다는 이유로 Cluster Scheduler가 생긴 것은 아니다.
- Ray Cluster가 구성됐다는 이유로 Tenant Queue와 GPU Quota 정책이 생긴 것은 아니다.
- Kubernetes Deployment Replica 수를 늘렸다는 이유로 하나의 Model이 여러 Node에 분할된 것은 아니다.
- Kueue가 Quota를 승인했다는 이유로 모든 Pod의 물리 배치가 보장된 것은 아니다.
- `nvidia.com/gpu: 1`이라는 표기가 항상 물리 GPU 하나를 뜻하지는 않는다.
- Time-Sharing의 Replica 수는 Compute 또는 VRAM의 보장된 분할 수가 아니다.
- MPS의 동시 실행은 MIG와 같은 Hardware 격리를 뜻하지 않는다.
- MIG Profile이 존재해도 Model의 KV Cache와 Workspace까지 수용한다는 뜻은 아니다.

## 9. 구축 및 검증 항목

### 9.1. 구축 전

1. Online Service인지 완료형 Batch Job인지 구분한다.
2. 하나의 Model Replica가 필요한 총 VRAM과 GPU 수를 계산한다.
3. TP, PP, DP와 Replica 수를 구분해 배치도를 작성한다.
4. Node당 GPU 수, GPU Interconnect와 NIC Topology를 확인한다.
5. Cluster Queue, Quota, Priority와 Preemption 소유자를 정한다.
6. Exclusive, Time-Sharing, MPS 또는 MIG 중 GPU 노출 방식을 정한다.
7. Driver, CUDA, Runtime, Scheduler와 CRD Version을 고정한다.
8. Model, Container와 Dataset 배포 경로를 결정한다.
9. Private Network, Port, TLS와 인증 경계를 설계한다.
10. Node·GPU 장애 시 Job 재시작 또는 Service 우회 방식을 정한다.

### 9.2. 기능 검증

```text
Node에서 GPU 인식
→ Container에서 GPU 인식
→ Scheduler Resource 등록
→ 단일 GPU Workload 실행
→ Multi-GPU Rank와 Binding 확인
→ Multi-node 통신 확인
→ Queue·Quota와 Gang 동작 확인
→ Model Load와 Warm-up
→ 실제 요청 또는 Job 실행
```

명령 예시는 다음과 같다.

```bash
nvidia-smi -L
nvidia-smi topo -m
kubectl describe node <GPU_NODE>
kubectl get pods -A -o wide
kubectl get events -A --sort-by=.lastTimestamp
sinfo -N -o '%N %t %G'
squeue
ray status
```

사용하지 않는 Platform의 명령은 생략한다. 각 계층을 통과했는지 확인한 뒤 상위 계층으로 이동한다.

### 9.3. 성능과 격리 검증

| 시험 | 확인 Metric |
| --- | --- |
| 단일 GPU 기준선 | VRAM Peak, GPU Utilization, TTFT·TPOT 또는 Job Time |
| GPU 수 증가 | Token/sec, Step Time, Scaling Efficiency, Collective 시간 |
| Node 수 증가 | Network Throughput, NCCL 시간, p99 Latency |
| 공유 Workload 증가 | Workload별 Throughput, p95·p99, OOM과 Fairness |
| Node 장애 | 감지 시간, Job 상태, Replica 우회와 복구 시간 |
| GPU Error·Process Crash | 같은 GPU·MIG·MPS Client에 미치는 영향 |
| Queue 경쟁 | 대기 시간, Priority, Borrowing, Preemption과 Starvation |
| Cold Start | Node Provisioning, Image Pull, Model Download와 Load 시간 |

GPU가 모두 사용 중이라는 사실만으로 효율적이라는 결론을 내리지 않는다. 완료 시간, 요청 SLO, 실패율과 비용을 함께 본다.

### 9.4. 장애 확인 순서

| 증상 | 확인 순서 |
| --- | --- |
| GPU Pod·Job Pending | GPU Resource 이름 → Node Label·Taint → Queue Admission → 실제 Capacity |
| Ray Worker 미등록 | Private IP → Port·Firewall → Container Network → Ray Version·Address |
| vLLM Rank 시작 실패 | 총 GPU 수 → TP×PP → Model Path → Shared Memory → Driver 호환성 |
| NCCL Hang | Rank 수 → NIC 이름 → Routing·Firewall → RDMA → Topology |
| Kueue 승인 후 Pod Pending | TAS → Node Fragmentation → Affinity·Taint → Autoscaler |
| Volcano Job Pending | Queue Open 상태 → PodGroup `minMember` → Plugin → Node Resource |
| 공유 GPU OOM | Workload별 VRAM Peak → 공유 수 → Context·Batch → 격리 방식 |
| 공유 후 Tail Latency 증가 | 동시 Peak → Time-Sharing·MPS 경쟁 → CPU·Memory·Network 경쟁 |
| MIG Pod Pending | GPU 지원 → Profile 이름 → Node Label → Device Plugin Strategy |

## 10. 정리

- Docker + vLLM + Ray는 여러 GPU Node에 하나의 LLM을 TP·PP로 분산하는 Runtime 구성이다.
- vLLM Native Multi-node는 같은 분산 추론 범주의 대체 Backend이며 별도 Cluster 종류로 분류하지 않는다.
- Slurm은 GPU Batch·HPC Cluster의 Allocation, Queue와 Job Scheduling을 담당한다.
- Kubernetes는 GPU Node에 Containerized Service와 Job을 배치하지만 기본 Scheduler는 Pod 단위로 동작한다.
- Kueue는 Queue·Quota·Admission을 기존 Kubernetes Scheduler 앞에 추가하고, Volcano는 Batch Scheduler와 Job·Queue 체계를 제공한다.
- Kubernetes 1.37 Native Gang Scheduling은 Beta이지만 기본 비활성화이며 Queue·Quota 제품 전체를 대체하지 않는다.
- Exclusive GPU, Time-Sharing, MPS와 MIG는 Cluster 종류가 아니라 Node 안에서 GPU를 노출하는 방식이다.
- GKE Time-Sharing과 MPS는 T4·L4에서 사용할 수 있지만 이에 한정되지 않는다. GKE MIG는 현재 T4·L4를 지원하지 않는다.
- GPU 공유는 VRAM을 늘리는 방법이 아니며 성능, Memory, 장애와 Tenant 격리 수준으로 선택한다.

## 11. References

공식 문서의 제품 상태와 지원 범위는 2026-09-15에 확인했다.

- vLLM, [Parallelism and Scaling](https://docs.vllm.ai/en/latest/serving/parallelism_scaling/)
- vLLM, [Data Parallel Deployment](https://docs.vllm.ai/en/stable/serving/data_parallel_deployment/)
- Ray, [Serving LLMs](https://docs.ray.io/en/latest/serve/llm/index.html)
- Ray, [Cross-node Parallelism](https://docs.ray.io/en/latest/serve/llm/user-guides/cross-node-parallelism.html)
- NVIDIA, [NCCL User Guide](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/)
- NVIDIA, [GPUDirect RDMA](https://docs.nvidia.com/cuda/gpudirect-rdma/)
- SchedMD, [Slurm Workload Manager Overview](https://slurm.schedmd.com/overview.html)
- SchedMD, [Generic Resource Scheduling](https://slurm.schedmd.com/gres.html)
- SchedMD, [Multifactor Priority](https://slurm.schedmd.com/priority_multifactor.html)
- SchedMD, [Resource Limits](https://slurm.schedmd.com/resource_limits.html)
- Kubernetes, [Schedule GPUs](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- Kubernetes, [Assigning Pods to Nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- Kubernetes, [Scheduling Group](https://kubernetes.io/docs/concepts/workloads/pods/scheduling-group/)
- Kubernetes, [Kubernetes v1.37 Release](https://kubernetes.io/blog/2026/08/26/kubernetes-v1-37-release/)
- NVIDIA, [Kubernetes Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- NVIDIA, [GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/)
- Kueue, [Concepts](https://kueue.sigs.k8s.io/docs/concepts/)
- Kueue, [Quick Start](https://kueue.sigs.k8s.io/docs/getting-started/quick-start/)
- Kueue, [Cluster Queue](https://kueue.sigs.k8s.io/docs/concepts/cluster_queue/)
- Kueue, [All-or-nothing Scheduling](https://kueue.sigs.k8s.io/docs/concepts/all_or_nothing/)
- Volcano, [Scheduler Overview](https://volcano.sh/docs/scheduler/overview/)
- Volcano, [Queue](https://volcano.sh/docs/concepts/queue/)
- Volcano, [PodGroup](https://volcano.sh/docs/concepts/podgroup/)
- Volcano, [Gang Scheduling Plugin](https://volcano.sh/docs/scheduler/plugins/gang/)
- Google Cloud, [About GPU Sharing Strategies in GKE](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/timesharing-gpus)
- Google Cloud, [Share GPUs with GPU Time-Sharing](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/timesharing-gpus)
- Google Cloud, [Share GPUs with NVIDIA MPS](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/nvidia-mps-gpus)
- Google Cloud, [Running Multi-instance GPUs](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/gpus-multi)
