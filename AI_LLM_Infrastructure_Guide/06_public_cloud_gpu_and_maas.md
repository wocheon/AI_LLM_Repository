# Public Cloud GPU와 MaaS

Public Cloud에서 AI Model을 사용하는 방법은 GPU VM을 직접 운영하는 방식부터 Provider가 Model Runtime까지 운영하는 API 방식까지 이어진다. 이 문서는 AWS, Microsoft Azure와 Google Cloud의 제공 계층, GPU Capacity 확보 조건, MaaS의 호출·Network·데이터 경계와 선택 기준을 정리한다.

GPU SKU, Model Catalog, Region, Quota와 가격은 자주 바뀐다. 본문은 변하지 않는 확인 방법을 중심으로 설명하며, 제품 상태와 명칭은 2026-09-15 기준이다.

## 1. Public Cloud의 AI Model 제공 계층

### 1.1. GPU VM

GPU VM은 GPU가 연결된 Virtual Machine을 빌리는 IaaS 방식이다. 사용자는 일반적으로 다음 항목을 관리한다.

- OS Image, Kernel, GPU Driver와 가속기 Runtime
- Container Runtime, Framework와 Model Serving Runtime
- Model Artifact의 Download, Version, License와 저장 위치
- Process 배치, Multi-GPU 통신, Health Check와 Auto Scaling
- 보안 Patch, 장애 복구, Log·Metric 수집과 비용 최적화

Cloud Provider는 물리 Host, GPU 장착과 VM Virtualization을 관리한다. 그러나 VM 안에서 Model Server가 정상 실행되는지, VRAM이 충분한지, Driver와 Framework가 호환되는지는 사용자의 책임이다.

GPU VM은 Custom Kernel, 특정 Runtime, 직접 보유한 Weight와 상세한 Network 구성이 필요할 때 적합하다. 반면 작은 Traffic에도 VM이 실행 중인 시간만큼 비용이 발생하고, Node 교체와 Capacity 부족에 대응해야 한다.

### 1.2. Managed Kubernetes의 GPU Node

Amazon EKS, Azure Kubernetes Service와 Google Kubernetes Engine은 Kubernetes Control Plane 운영 일부를 Provider에 맡긴다. GPU 연산 자체는 각 Cloud의 GPU VM으로 만든 Worker Node에서 실행된다.

```text
Managed Kubernetes Control Plane
                │ Scheduling·Node 관리
                v
GPU Node Pool ──> Driver·Device Plugin ──> Pod ──> Model Runtime
     │                                      │
     └─ VM SKU·Zone·Quota·Capacity          └─ GPU Resource Request
```

Managed Kubernetes를 사용해도 GPU VM의 Region·Zone별 가용성, Quota와 Capacity 제약은 사라지지 않는다. Node Group 또는 Node Pool이 생성되지 않으면 Pod Auto Scaling만으로 GPU를 늘릴 수 없다.

사용자는 다음 항목을 별도로 확인한다.

- Node Image와 GPU Driver 설치 주체
- NVIDIA Device Plugin 또는 GPU Operator의 설치·Upgrade 주체
- `nvidia.com/gpu` Resource, Taint, Toleration과 Node Affinity
- GPU Node Pool의 최소·최대 수와 Scale-up 시간
- Model Artifact 배포와 Pod 시작 시간이 Auto Scaling에 미치는 영향
- Pod가 아니라 GPU Node 또는 Multi-GPU Group 단위로 복구해야 하는 장애

### 1.3. Managed AI Compute와 Endpoint

Managed AI Compute는 사용자가 Model 또는 Container와 배포 설정을 제출하면 Provider가 Endpoint, Replica와 일부 Runtime 운영을 관리하는 계층이다. 대표적인 예는 SageMaker AI 실시간 Endpoint, Azure Machine Learning Managed Online Endpoint, Microsoft Foundry Managed Compute와 Vertex AI Endpoint다.

제품별 관리 범위는 같지 않다. 어떤 서비스는 사용자가 VM Type과 Instance 수를 선택하고, 어떤 서비스는 Model 중심의 크기나 처리량만 받는다. 다음 항목을 제품별로 확인해야 한다.

| 항목 | 확인 질문 |
| --- | --- |
| Artifact | 사용자가 Weight를 제공하는가, Catalog Model을 참조하는가? |
| Runtime | Custom Container를 허용하는가, Provider Runtime만 사용하는가? |
| Compute | GPU SKU를 직접 선택하는가, Provider가 내부에서 결정하는가? |
| Scale | 최소 Replica, Scale-to-zero와 최대 Replica를 제어할 수 있는가? |
| Network | Public Endpoint 차단과 Private Endpoint를 지원하는가? |
| 운영 | Patch, Runtime Upgrade, Replica 교체와 Rollback의 책임은 누구에게 있는가? |

`Managed`는 Model 품질이나 SLO가 자동으로 충족된다는 뜻이 아니다. Cold Start, Model Load, Auto Scaling 반응, Traffic 분산과 배포 중 가용성은 실제 Payload로 시험한다.

### 1.4. Model as a Service

MaaS는 Provider가 보유하거나 계약한 Model을 Network API로 호출하는 방식이다. 사용자는 일반적으로 GPU SKU, Driver, Weight와 Serving Runtime을 관리하지 않는다.

MaaS의 주요 운영 단위는 GPU 수가 아니라 다음 항목이다.

- Model ID, Version과 Deployment ID
- 입력·출력 Token 또는 Image·Audio 같은 과금 단위
- Request/Token Rate Limit과 동시 요청 제한
- On-demand 또는 공유 처리량과 Provisioned Throughput
- 호출 Region과 실제 데이터 처리 Geography
- API 인증, Private Network 지원과 Provider의 데이터 처리 정책

MaaS가 `Serverless`로 표시되어도 내부 Compute가 없다는 뜻은 아니다. Provider가 Runtime과 가속기를 운영하고 사용자는 API 사용량 또는 예약한 처리량에 대해 지불한다는 의미다.

### 1.5. 계층별 사용자 관리 범위

| 관리 항목 | GPU VM | Managed Kubernetes | Managed AI Compute | MaaS |
| --- | --- | --- | --- | --- |
| Model Weight 선택 | 사용자 | 사용자 | 사용자 또는 Catalog | Catalog·허용 Version |
| Serving Runtime | 사용자 | 사용자 | 사용자 또는 Provider | Provider |
| GPU Driver | 사용자 | 사용자·Provider 분담 | Provider | Provider |
| Workload Scheduler | 사용자 | 사용자 | Provider와 설정 분담 | Provider |
| Replica·Node Scaling | 사용자 | 사용자 | 정책은 사용자, 실행은 Provider | Provider 또는 처리량 구매 |
| GPU SKU·Topology | 직접 선택 | Node SKU로 선택 | 제품에 따라 선택 | 노출하지 않음 |
| OS Patch | 사용자 | Node 범위 사용자·Provider 분담 | Provider | Provider |
| Model API Schema | 사용자 | 사용자 | Runtime에 따라 결정 | Provider가 결정 |
| Capacity 확보 | Quota·예약·배포 | Node Quota·예약·배포 | Endpoint Quota·Capacity | Rate Limit·Provisioned Capacity |
| 미사용 비용 | 실행 VM 전체 | Node와 Control Plane | 최소 Replica·Compute | Provisioned 사용 시 발생 |

관리 계층이 높아질수록 Hardware 제어와 Runtime Portability는 줄어드는 대신 Host 운영 범위가 작아진다. 어느 계층이 더 적합한지는 Model Artifact 통제, 성능 목표, Traffic 모양, 데이터 경계와 운영 인력으로 판단한다.

## 2. AWS

### 2.1. EC2 Accelerated Computing Instance

Amazon EC2의 Accelerated Computing Instance에는 GPU, FPGA와 AWS 자체 가속기가 포함된다. GPU가 필요한 Workload라면 Instance Family 이름만 보지 말고 각 Instance Type의 실제 Accelerator를 확인한다.

AI/ML에서 자주 검토하는 범주는 다음과 같다.

| 범주 | 주 용도 | 확인할 항목 |
| --- | --- | --- |
| P 계열 | 대규모 학습, HPC, 대형 추론 | GPU 세대·수, GPU Memory, GPU Interconnect, EFA |
| G 계열 | 추론, Graphics, 중소 규모 학습 | GPU Memory, Fractional 제공 여부, Encoding·Graphics 기능 |
| Inf 계열 | AWS Inferentia 기반 추론 | Neuron Runtime과 Model 지원 범위 |
| Trn 계열 | AWS Trainium 기반 학습·추론 | Neuron SDK, 분산 구성과 Compiler 지원 |

Inf와 Trn은 GPU가 아니다. CUDA 전용 Container를 그대로 실행할 수 있다고 가정하지 않는다. Compiler와 Operator 지원, Model 변환 및 성능 검증을 별도로 수행한다.

EC2 공식 Specification에서 다음 값을 한 행으로 수집한다.

- Accelerator Type·수·Memory
- vCPU와 System Memory
- GPU 간 연결 구조와 EFA 지원
- Network의 Baseline·Maximum Bandwidth
- EBS Bandwidth·IOPS와 Local Instance Store
- CPU Architecture와 지원 OS

### 2.2. GPU Instance Family와 고정 Instance Type

EC2 Instance Type은 GPU만 선택한 뒤 CPU와 RAM을 자유롭게 붙이는 구조가 아니다. 예를 들어 같은 Family 안에서도 `.xlarge`, `.12xlarge`, `.48xlarge`에 따라 GPU 수, vCPU, RAM, NIC와 EBS 처리량이 묶여 있다.

따라서 `GPU 1장 가격`만 비교하지 않는다. Model Server가 CPU Tokenization 또는 Storage Load에 막히면 더 큰 Type이 필요할 수 있고, Multi-GPU Type은 GPU 수 외에 내부 Topology가 성능을 좌우한다.

Instance 후보표에는 다음을 기록한다.

```text
Region / Availability Zone
Instance Type / CPU Architecture
GPU Type / GPU Count / VRAM per GPU
vCPU / RAM
GPU Interconnect / EFA
Network / EBS / Instance Store
On-demand·Spot·Capacity Reservation 지원 여부
Quota 이름 / 현재 Limit
확인 날짜 / 공식 Specification URL
```

같은 Type도 모든 Availability Zone에서 제공되지 않는다. Region 지원과 실제 Zone Offering을 분리해서 확인한다.

### 2.3. EKS와 SageMaker의 GPU 사용 방식

EKS의 GPU Node는 EC2 Instance다. Managed Node Group 또는 Karpenter가 Node를 만들더라도 EC2의 Instance Offering, vCPU Quota와 Capacity를 사용한다. GPU Node에 Driver와 Device Plugin이 준비되어야 Pod가 `nvidia.com/gpu`를 요청할 수 있다.

EKS에서 확인할 항목은 다음과 같다.

- 여러 호환 Instance Type과 Availability Zone을 허용할 수 있는지
- GPU Node용 AMI, Driver와 Device Plugin Version
- Node Taint와 Pod Toleration
- Model Download 전용 Init 단계와 Node Scale-up 시간
- Spot 중단 신호를 받을 때 Drain과 Checkpoint가 가능한지
- Multi-node Training의 Placement와 EFA 구성이 필요한지

SageMaker AI Hosting은 Model, Container Image, Endpoint Configuration과 Endpoint를 분리한다. Endpoint Configuration에서 Instance Type과 초기 Instance 수를 정하고, Application Auto Scaling으로 Replica를 조절할 수 있다. 사용자는 Container와 Model 성능, 최소·최대 Instance 수, Scale Metric, 배포 Version과 Load Test를 관리한다.

Production Endpoint는 단일 Instance 장애뿐 아니라 Availability Zone 장애 조건도 검토한다. 여러 Instance를 배치해도 Model Server 내부의 Memory Leak이나 잘못된 Artifact가 모든 Replica에 공통으로 발생할 수 있으므로 Version Rollback 경로가 필요하다.

### 2.4. Amazon Bedrock MaaS

Amazon Bedrock은 Foundation Model을 Bedrock Runtime API로 호출하게 한다. Model별로 지원 Region, 입력 형식, Context, Streaming, Provisioned Throughput와 Customization 지원 범위가 다르다.

주요 호출 방식은 다음과 같이 구분한다.

| 방식 | 처리량 특성 | 운영 확인 사항 |
| --- | --- | --- |
| On-demand | 공유 Capacity와 Model별 Quota 사용 | RPM·TPM, `429`, Retry와 Region 가용성 |
| Cross-Region Inference Profile | 허용된 여러 Region으로 요청 Route | 목적지 Region, IAM Resource와 데이터 Geography |
| Provisioned Throughput | 특정 Model 처리량을 일정 기간 확보 | Model Unit, 약정 기간, 미사용 비용과 지원 Version |
| Batch Inference | 비동기 대량 처리 | Input·Output 저장소, 완료 시간과 Job Quota |

새 Application은 Bedrock Runtime의 Converse 계열 또는 Model에 맞는 통합 API를 검토한다. IAM에는 필요한 Model 또는 Inference Profile의 호출 Action과 Resource만 허용한다. Model ID 문자열을 Application 여러 곳에 직접 넣지 말고 배포 설정으로 관리한다.

Cross-Region Inference는 가용 Capacity를 넓힐 수 있지만 요청이 Source Region 밖에서 처리될 수 있다. Geography가 고정된 Profile도 허용 목적지 목록과 Abuse Detection 관련 저장 조건을 공식 문서에서 확인한다.

### 2.5. Region, Quota와 Capacity 확인

AWS에서는 최소한 다음 네 조건을 별도로 통과해야 한다.

1. 대상 Instance Type 또는 Bedrock Model이 Region에 존재한다.
2. Account의 Service Quota가 요청량 이상이다.
3. 지정 Availability Zone에 현재 물리 Capacity가 있거나 예약이 활성화되어 있다.
4. IAM, Network와 조직 Policy가 생성 또는 호출을 허용한다.

EC2 Offering과 Quota를 조회하는 예시는 다음과 같다.

```bash
aws ec2 describe-instance-type-offerings \
  --region <REGION> \
  --location-type availability-zone \
  --filters Name=instance-type,Values=<INSTANCE_TYPE>

aws service-quotas list-service-quotas \
  --service-code ec2 \
  --region <REGION>
```

`describe-instance-type-offerings` 결과는 해당 Type을 Offering한다는 뜻이지, 요청 시점에 필요한 수량을 즉시 생성할 수 있다는 보장은 아니다. 실제 Capacity는 소규모 검증 생성, Fleet 요청 또는 Capacity Reservation 승인 결과로 확인한다.

Bedrock은 Model Catalog, Model별 Region 표와 Runtime Quota를 함께 본다. On-demand와 Cross-Region Inference의 Token·Request Quota는 별도일 수 있으며 새 Account의 기본값도 다를 수 있다.

## 3. Microsoft Azure

### 3.1. GPU Accelerated VM Size

Azure의 GPU VM은 N 계열 Size로 제공된다. VM Size 하나에 GPU Type·수, vCPU, RAM, Local Disk, Network와 Remote Storage 제한이 결합된다.

후보 Size를 선택할 때 다음을 확인한다.

- 전체 GPU인지 Fractional GPU인지
- GPU당 Memory와 VM 전체 GPU 수
- GPU 간 NVLink 또는 InfiniBand·RDMA 지원
- Accelerated Networking과 NIC Bandwidth
- Local NVMe 유무와 Managed Disk 제한
- 지원 OS Image와 Driver 설치 방식
- 해당 Size의 Region·Zone 제한과 Retirement 공지

Azure 문서는 Family, Series와 Size를 구분한다. `NC`라는 Family 이름만으로 GPU 세대와 Memory를 결정할 수 없으며 `v4`, `v5`, Accelerator 이름까지 포함한 정확한 Size를 기록한다.

### 3.2. NC·ND·NV Family의 용도 구분

| Family | 일반적인 설계 목적 | AI/LLM 검토 관점 |
| --- | --- | --- |
| NC | GPU Compute, 중소 규모 학습·추론과 HPC | GPU Memory, 단일·다중 GPU, RDMA 지원을 Series별 확인 |
| ND | 대규모 Deep Learning, 분산 학습·추론 | 고성능 GPU, GPU Fabric와 InfiniBand Topology 확인 |
| NV | Visualization, VDI, Graphics | Graphics License와 Fractional GPU, CUDA 추론 적합성 확인 |

이 구분은 후보를 좁히는 용도다. 특정 Series의 공식 Specification이 최종 기준이다. NVIDIA 기반 NV Series는 CUDA Compute도 수행할 수 있지만, AMD GPU를 사용하는 Series에는 CUDA를 적용할 수 없다. Accelerator Vendor, Graphics 중심의 CPU·RAM·Network 조합과 LLM Runtime 호환성을 함께 확인한다.

Retirement가 공지된 Size는 신규 배포 후보에서 제외하고 Migration 날짜를 기록한다. 단순히 VM이 현재 생성된다는 이유로 장기 운영 가능성을 가정하지 않는다.

### 3.3. AKS와 Managed AI Compute의 GPU 사용 방식

AKS GPU Node Pool은 Azure GPU VM Size를 사용한다. Node Pool 생성에는 Subscription의 Region별 Total vCPU Quota와 해당 VM Family vCPU Quota가 모두 필요하고, 실제 Region·Zone Capacity도 있어야 한다.

AKS의 Driver와 Device Plugin 설치 방식은 Cluster·Node Image와 기능에 따라 달라진다. 자동 설치를 사용할 때도 다음을 배포 기록에 남긴다.

- AKS와 Node Image Version
- GPU Driver와 Device Plugin Version
- MIG, Time-slicing 또는 MPS 사용 여부
- Node Pool의 Zone, VM Size, Taint와 Auto Scaling 범위
- Upgrade·Node 재생성 시 GPU Workload Drain 방식

Managed AI Compute에는 여러 제품이 포함된다. Azure Machine Learning Managed Online Endpoint는 Model과 Container를 Compute Instance에 배포하는 방식이고, Microsoft Foundry의 Managed Compute는 Catalog의 Open Model을 전용 GPU Runtime에 배포하는 방식이다.

Microsoft Foundry Managed Compute는 2026-09-15 기준 Public Preview다. SLA가 없는 Preview 기능을 Production 기본 경로로 가정하지 않고, 지원 Model·Region·Network와 GA 전환 상태를 재확인한다.

### 3.4. Microsoft Foundry Models MaaS

Microsoft Foundry Models는 Catalog Model을 Serverless API Deployment로 제공한다. 2026-09-15 기준 문서에서는 Serverless API가 주요 배포 경로이며, Model과 Region에 따라 다음 Deployment Type을 선택할 수 있다.

| Deployment Type | 데이터 처리 범위 | 과금·처리량 특성 |
| --- | --- | --- |
| Global Standard | Azure가 Global Region으로 Route | Token 기반 공유 처리량 |
| Data Zone Standard | 정의된 Data Zone 내부 | Token 기반 공유 처리량 |
| Standard | 선택한 단일 Region | Token 기반 공유 처리량 |
| Global·Data Zone·Regional Provisioned | 선택한 범위에 따라 처리 | PTU 기반 전용 처리량 |
| Batch | 비동기 처리 | Batch 단위 Token 과금 |

모든 Model이 모든 Deployment Type과 Region을 지원하지 않는다. Model Version, 배포 SKU와 처리 Geography를 한 묶음으로 고정한다.

Foundry Project Endpoint는 API Key 또는 Microsoft Entra ID Token으로 호출할 수 있다. 운영 환경에서는 Workload Identity 또는 Managed Identity와 최소 권한 RBAC를 우선 검토하고, Key를 사용할 경우 Secret Store와 Rotation을 적용한다.

Provisioned Throughput Unit은 Model 간 동일한 Token/sec 단위가 아니다. Model·Version, 입력·출력 비율과 Cached Token에 따라 필요한 PTU가 달라지므로 Foundry Capacity Calculator와 실제 부하 시험을 사용한다.

### 3.5. Region, Quota와 Capacity 확인

Azure VM 배포는 Quota와 Capacity를 별도로 검사한다. Quota는 Subscription이 Region에서 사용할 수 있는 권한이고, Capacity는 해당 Region 또는 Zone에 실제로 배치할 수 있는 Compute다.

다음 명령은 후보 VM Size와 Quota를 확인하는 출발점이다.

```bash
az vm list-skus \
  --location <REGION> \
  --resource-type virtualMachines \
  --all \
  --output table

az vm list-usage \
  --location <REGION> \
  --output table
```

`list-skus`의 `Restrictions`와 Zone 정보를 확인한다. Quota는 Total Regional vCPU와 대상 N Family vCPU를 모두 만족해야 한다. Quota가 충분해도 `AllocationFailed` 또는 유사 Capacity 오류가 발생할 수 있다.

중요한 상시 Workload는 On-demand Capacity Reservation 지원 Size와 Zone을 확인한다. Azure Reserved VM Instance는 비용 할인 상품이며 Compute Capacity를 보장하지 않으므로 같은 의미로 사용하지 않는다.

Foundry Models는 Model별 Region Availability, Deployment Type 지원, TPM·RPM 또는 PTU Quota와 실제 배포 Capacity를 확인한다. Global 또는 Data Zone Deployment를 사용하면 Resource 생성 Region과 실제 처리 위치가 같다고 가정하지 않는다.

## 4. Google Cloud

### 4.1. Compute Engine GPU Machine

Google Compute Engine에서 GPU를 사용하는 방식은 Accelerator-optimized Machine과 일부 General-purpose Machine에 GPU를 연결하는 방식으로 나뉜다.

공통 확인 항목은 다음과 같다.

- Machine Series와 정확한 Machine Type
- GPU Type·수·Memory와 CPU·RAM 비율
- GPU 간 연결과 GPUDirect·Network 지원
- Persistent Disk·Local SSD 처리량과 수명주기
- Host Maintenance 시 정지 조건과 Local SSD 데이터 처리
- Zone별 GPU Type Availability와 Quota
- Driver 설치 Image와 CUDA 호환성

GPU가 연결된 VM은 Host Maintenance 동작이 일반 VM과 다를 수 있다. Maintenance Event에서 Instance 정지와 Local SSD 손실 가능성을 포함해 Checkpoint와 재시작 절차를 설계한다.

### 4.2. Accelerator-optimized Machine과 GPU 연결형 VM

Accelerator-optimized A·G 계열은 Machine Type에 특정 GPU 수, vCPU와 Memory가 미리 결합되어 있다. 대형 Multi-GPU Type은 내부 GPU Fabric와 NIC Topology까지 하나의 설계 단위다.

일부 GPU는 N1 General-purpose Machine에 연결할 수 있다. 이 방식은 CPU·RAM 조합의 선택 폭이 더 크지만 모든 GPU Type이나 최신 Platform에 적용되는 것은 아니다.

| 방식 | 장점 | 제약 |
| --- | --- | --- |
| Accelerator-optimized | GPU 중심으로 검증된 고정 구성, Multi-GPU 연결 | Machine Type별 GPU 수·CPU·RAM이 고정됨 |
| N1 + Attached GPU | 일부 GPU에서 CPU·RAM 조합 선택 가능 | 지원 GPU·Zone·Machine 조건이 제한됨 |

현재 Series 이름을 장기 설계 기준으로 고정하지 않는다. Compute Engine의 Accelerator-optimized Machine 표에서 지원 GPU, Provisioning Model, Reservation 방식과 Zone을 확인한다.

### 4.3. GKE와 Vertex AI의 GPU 사용 방식

GKE Standard GPU Node Pool은 Compute Engine GPU Machine을 사용한다. Node Pool은 GPU Type이 제공되는 Zone에 배치하고, 자동 또는 수동 방식으로 Driver를 설치한다.

GKE에서는 다음 조건을 함께 설정한다.

- GPU Node Pool을 일반 Node Pool과 분리
- `nvidia.com/gpu=present:NoSchedule` Taint와 필요한 Toleration
- Pod의 GPU Resource Limit과 Node Affinity
- Node Auto Scaling 범위와 GPU가 없는 Zone으로의 잘못된 확장 방지
- Driver Version과 Node OS Image의 호환성
- Spot, Reservation 또는 다른 Consumption Option의 중단·시작 조건

Vertex AI Custom Training과 Endpoint는 Google 관리 Control Plane 위에서 지정 Machine과 Accelerator를 사용한다. 사용자는 Training Container 또는 Model Artifact, Machine Spec, Replica와 Auto Scaling 설정을 제공하고, Provider가 Job·Endpoint Lifecycle 일부를 관리한다.

Managed Endpoint도 GPU Quota와 Machine Availability 영향을 받을 수 있다. 배포 생성 성공, Replica Scale-out 시간, Model Load와 Rolling Update 동작을 Production Payload로 확인한다.

### 4.4. Vertex AI MaaS

Vertex AI Model Garden은 Google Model과 일부 Partner·Open Model의 탐색·배포 경로를 제공한다. 그중 Provider가 운영하는 Model API는 사용자가 GPU VM을 직접 선택하지 않고 Publisher Model ID와 Location을 지정해 호출한다.

Managed Generative AI Model의 처리량 방식은 다음과 같이 구분한다.

| 방식 | 처리량 특성 | 실패·비용 관점 |
| --- | --- | --- |
| Pay-as-you-go | Dynamic Shared Quota의 공유 Pool 사용 | 수요가 높으면 `429 resource exhausted`, Retry 필요 |
| Provisioned Throughput | Project·Location·Model·Version에 GSU 할당 | 고정 비용, 미사용 처리량은 누적되지 않음 |
| Batch Prediction | 비동기 대량 요청 | 완료 시간, Input·Output Storage와 Job 제한 |

Provisioned Throughput는 Query 수만으로 산정하지 않는다. 입력과 출력 Token, Image·Audio 같은 Modality별 Burndown Rate를 적용한 처리량으로 GSU를 계산한다.

Model별 Endpoint, API Schema, Context, Region, Provisioned Throughput 지원과 Lifecycle이 다르다. Model Garden 화면에 보인다는 사실만으로 현재 Project·Location에서 MaaS 호출이 가능하다고 판단하지 않는다.

### 4.5. Region, Zone, Quota와 Capacity 확인

Compute Engine GPU는 Project의 Global GPU Quota와 Region·GPU Type별 Quota를 함께 확인한다. Standard, Spot, Reservation 또는 Commitment 사용량에 서로 다른 Quota가 적용될 수 있다.

후보 GPU와 Region 정보를 조회하는 예시는 다음과 같다.

```bash
gcloud compute accelerator-types list \
  --filter="zone:(<ZONE>)"

gcloud compute regions describe <REGION>

gcloud compute machine-types list \
  --filter="zone:(<ZONE>)"
```

목록과 Quota는 생성 권한을 보여줄 뿐 현재 물리 Capacity를 보장하지 않는다. 중요한 Workload는 대상 Zone의 Reservation 생성 성공과 실제 VM 또는 Cluster 생성 시험으로 확인한다.

Vertex AI는 Model별 지원 Location과 Dynamic Shared Quota 또는 Provisioned Throughput 조건을 확인한다. Provisioned Throughput는 Project·Location·Model·Version에 결합되므로 다른 Location 호출이 예약 처리량을 소비한다고 가정하지 않는다.

## 5. GPU Capacity 확보 방식

### 5.1. On-demand

On-demand는 장기 약정 없이 실행한 Compute에 대해 지불하는 기본 방식이다. 시작과 종료가 자유롭지만 특정 GPU를 원하는 시점에 만들 수 있다는 Capacity 보장은 아니다.

On-demand가 적합한 경우는 다음과 같다.

- 개발·검증처럼 실행 기간이 짧고 불규칙하다.
- 여러 호환 GPU Type, Region 또는 Zone으로 이동할 수 있다.
- 지연 시작을 허용하거나 Queue에서 대기할 수 있다.
- 장기 약정 전에 실제 사용률과 성능을 측정해야 한다.

Production 최소 Replica나 시작 시간이 고정된 학습 작업에는 단순 On-demand 생성만 의존하지 않는다. 생성 실패 때 사용할 대체 SKU·Zone과 예약 방식을 준비한다.

### 5.2. Reservation과 Capacity Reservation

`Reservation`은 Provider마다 비용 약정과 물리 Capacity 예약을 모두 가리킬 수 있다. 이름 대신 무엇을 확보하는지 확인한다.

| Cloud | 비용 할인·사용 약정 | 물리 Capacity 확보 |
| --- | --- | --- |
| AWS | Savings Plans, Regional Reserved Instance 등 | EC2 On-Demand Capacity Reservation, 지원 대상 Capacity Blocks 등 |
| Azure | Azure Reservation·Reserved VM Instance, Savings Plan | On-demand Capacity Reservation |
| Google Cloud | Committed Use Discount | Standalone 또는 Commitment에 Attached된 Reservation |

일반 원칙은 다음과 같다.

- 할인 약정만 구매해도 VM 생성 Capacity가 없으면 배포가 실패할 수 있다.
- Capacity Reservation은 보통 특정 Region·Zone, SKU와 수량에 묶인다.
- 예약된 Capacity가 미사용이어도 비용이 발생할 수 있다.
- Quota가 부족하면 Capacity Reservation 요청 자체가 실패할 수 있다.
- 할인과 Capacity를 함께 얻으려면 Provider별 결합 조건을 확인한다.

AWS의 Zonal Reserved Instance처럼 예외적으로 비용 할인과 Zone Capacity 속성을 함께 가지는 상품도 있다. 모든 `Reserved Instance`에 같은 속성이 있다고 일반화하지 않는다.

### 5.3. Spot과 Preemptible Capacity

Spot은 Provider의 여유 Capacity를 할인된 가격으로 사용하며 회수될 수 있다. Google Cloud에서는 Spot VM이 기존 Preemptible VM의 최신 제공 방식이다.

공식 문서 기준 중단 사전 통지는 AWS Spot이 2분, Azure Spot과 Google Cloud Spot이 최대 약 30초 수준이다. 통지는 Best-effort 조건이 포함될 수 있으므로 이 시간 안에 큰 Checkpoint를 항상 완료할 수 있다고 가정하지 않는다.

Spot에 적합한 Workload는 다음과 같다.

- 재실행 가능한 Batch Inference와 데이터 전처리
- 짧은 간격으로 Checkpoint를 저장하는 Training
- Replica 일부가 사라져도 다른 Replica가 처리할 수 있는 Stateless Serving
- 시작 시각과 완료 시각이 유연한 실험

다음 조건에서는 중단 비용을 먼저 계산한다.

- Multi-node Training에서 Node 하나의 손실로 전체 Group이 재시작된다.
- Model Download와 Dataset 준비 시간이 실제 계산 시간보다 길다.
- Local Disk에만 Checkpoint가 있어 Instance 회수 시 복구할 수 없다.
- Online Serving의 최소 Capacity가 모두 Spot에 있다.

Spot Pool을 다양화할 때는 VRAM과 Runtime 호환성이 같은 후보만 묶는다. GPU 이름이 다르면 Quantization Kernel, Tensor Parallel 구성과 성능도 달라질 수 있다.

### 5.4. Quota 승인과 실제 물리 Capacity의 차이

GPU 배포 가능 여부는 다음 Gate를 순서대로 통과한다.

```text
Service·SKU가 Location에 존재
              ↓
Account·Project·Subscription Quota가 충분
              ↓
Zone의 실제 Capacity 또는 유효한 Capacity Reservation 존재
              ↓
IAM·Network·Policy와 Runtime 조건 충족
              ↓
VM·Node·Endpoint 생성 성공 및 Workload Ready
```

Quota 증가는 사용 권한의 증가다. 물리 GPU를 미리 할당하는 동작이 아니다. 반대로 Capacity Reservation이 승인되어도 Quota와 IAM이 부족하면 사용하지 못할 수 있다.

Capacity 요청 또는 지원 문의에는 다음 정보를 제공한다.

- Account·Project·Subscription ID와 Billing 관계
- 정확한 SKU, GPU 수와 Replica·Node 수
- Region·Zone과 허용 가능한 대체 Location
- 시작일, 종료일, 24시간 상시 여부와 Ramp-up 계획
- On-demand, Spot, Reservation과 Commitment 조건
- Single-node인지 Tightly Coupled Multi-node인지

### 5.5. GPU·Machine Type·Region·Zone 제약

GPU Capacity는 GPU 칩만의 재고가 아니다. 요청한 Machine Type의 CPU, RAM, NIC, Local Storage와 Host Topology 전체가 맞아야 한다.

Multi-GPU와 Multi-node Workload에서는 다음 제약이 추가된다.

- VM 내부 GPU 간 NVLink·NVSwitch 연결
- Node 간 RDMA, EFA 또는 InfiniBand 지원
- Placement Group, Cluster Placement와 Fabric Topology
- NIC 수·Bandwidth와 Storage Read Throughput
- 동일 Driver·Runtime을 지원하는 Node Image
- 모든 Rank를 동시에 확보하는 Gang Scheduling 조건

단일 GPU VM 하나를 만들 수 있다는 검증은 8-GPU Node 여러 대를 같은 Fabric에 배치할 수 있다는 검증이 아니다. 목표 규모 그대로 또는 대표 축소 규모로 Collective Benchmark와 재생성 시험을 수행한다.

## 6. MaaS 사용 구조

### 6.1. Model Catalog와 Model Version

Catalog의 Marketing Name만 기록하면 재현할 수 없다. 배포 기록에 다음 값을 남긴다.

| 항목 | 기록 내용 |
| --- | --- |
| Provider·Publisher | Cloud Provider와 실제 Model 제공자 |
| Model ID | API에 전달하는 정확한 ID |
| Version·Revision | 명시 Version, Alias 또는 자동 Upgrade 여부 |
| Deployment ID | Application이 호출하는 배포 이름 또는 ARN |
| Region·Processing Scope | Resource 위치와 실제 처리 가능 Geography |
| Lifecycle | GA, Preview, Deprecated, Retirement 날짜 |
| Capability | Context, Modality, Tool Calling, Structured Output |
| Commercial Terms | 가격 Meter, License와 Accept 조건 |
| Safety Policy | 기본 Filter와 변경 가능 범위 |
| Tokenizer | Token 추정·과금에 사용하는 Model별 규칙 |

`latest` Alias나 Version 생략은 Provider 정책에 따라 새 Model Revision을 가리킬 수 있다. 재현성과 회귀 검사가 중요하면 고정 가능한 Version을 사용하고 Upgrade 전에 Golden Dataset을 재평가한다.

Model을 찾을 수 없는 오류는 ID 오타 외에도 Region 미지원, Marketplace 약관 미승인, Model Access 미설정, Preview 등록 누락 또는 Retirement로 발생할 수 있다.

### 6.2. Serverless 호출과 Provisioned Throughput

세 Cloud의 명칭은 다르지만 운영 관점에서는 공유 처리량과 전용 처리량을 구분할 수 있다.

| 구분 | 공유·On-demand 처리량 | Provisioned Throughput |
| --- | --- | --- |
| Capacity | Provider의 공유 Pool 사용 | Model 처리량 Unit을 배포에 할당 |
| 비용 | 주로 입력·출력 사용량 | 예약 Unit과 시간·기간 기반 |
| Traffic | 작고 변동이 큰 요청에 유리 | 지속적이고 예측 가능한 요청에 유리 |
| 성능 | 수요에 따라 Throttle·Latency 변동 가능 | 구매 범위에서 예측 가능성을 높임 |
| 운영 | Retry, Rate Limit과 Burst 제어 | Unit 산정, Utilization과 미사용 비용 관리 |

Provisioned라는 이름만으로 모든 Latency가 보장되는 것은 아니다. Model별 입력·출력 비율, 긴 Context, Streaming, Batch와 동시에 처리하는 요청 수가 실제 처리량을 바꾼다.

다음 순서로 산정한다.

1. 실제 Traffic에서 입력·출력 크기와 요청률 분포를 수집한다.
2. Provider의 Model·Version별 Unit 산정 규칙을 적용한다.
3. 평균이 아니라 Peak와 Burst 조건으로 후보 Unit을 계산한다.
4. 같은 Region·Version·API Option으로 Load Test한다.
5. Throttle, TTFT, TPOT, End-to-end Latency와 Unit Utilization을 측정한다.
6. 성장 여유와 장애 시 Traffic 이동량을 더한다.

### 6.3. Endpoint, 인증과 호출 테스트

호출 경로는 `Application → 인증 → Cloud Endpoint → Deployment·Model`로 분리해서 시험한다. Console Playground 성공만으로 Production Identity와 Network 경로가 검증되지는 않는다.

AWS Bedrock의 최소 호출 형태는 다음과 같다. 실행 전 현재 Model 또는 Inference Profile ID와 Region을 넣는다.

```bash
aws bedrock-runtime converse \
  --region <REGION> \
  --model-id <MODEL_OR_INFERENCE_PROFILE_ID> \
  --messages '[{"role":"user","content":[{"text":"health check"}]}]' \
  --inference-config '{"maxTokens":16,"temperature":0}'
```

Microsoft Foundry Project Endpoint는 Entra ID Token을 사용해 다음과 같이 시험할 수 있다. `model`에는 배포 이름 또는 현재 API가 요구하는 Model 이름을 사용한다.

```bash
AZURE_AI_AUTH_TOKEN=$(az account get-access-token \
  --resource https://cognitiveservices.azure.com \
  --query accessToken \
  --output tsv)

curl -sS -X POST \
  "https://<FOUNDRY_RESOURCE>.services.ai.azure.com/api/projects/<PROJECT>/openai/v1/responses" \
  -H "Authorization: Bearer ${AZURE_AI_AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"model":"<DEPLOYMENT_NAME>","input":"health check","max_output_tokens":16}'
```

`generateContent`를 지원하는 Vertex AI Publisher Model은 Application Default Credentials 또는 OAuth Access Token으로 호출한다. Partner Model은 API Schema가 다를 수 있으므로 해당 Model Card의 예제를 사용한다.

```bash
GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -sS -X POST \
  "https://<LOCATION>-aiplatform.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/publishers/<PUBLISHER>/models/<MODEL_ID>:generateContent" \
  -H "Authorization: Bearer ${GCP_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"role":"user","parts":[{"text":"health check"}]}],"generationConfig":{"maxOutputTokens":16,"temperature":0}}'
```

Shell History와 CI Log에 API Key를 직접 남기지 않는다. 예제 Token도 저장소에 Commit하지 않는다. 운영에서는 Instance·Pod·Workload Identity를 사용하고 Token 발급 권한과 Model 호출 권한을 분리한다.

호출 테스트는 HTTP 성공 여부 외에 다음 값을 기록한다.

- Request ID, Model·Deployment ID와 처리 Region 정보
- HTTP Status와 Provider Error Code
- 입력·출력 Token, Cached Token과 과금 단위
- TTFT, End-to-end Latency와 Streaming 종료 상태
- Safety Filter 또는 출력 중단 사유
- Retry 횟수와 최종 성공 여부

### 6.4. Region, Quota와 Rate Limit

MaaS Limit은 Model, Region, Account·Project, Deployment Type과 API별로 다를 수 있다. `요청/분`만 확인하지 말고 입력·출력 Token Rate, 동시 요청, 일일 한도와 Batch Job 제한을 함께 확인한다.

`429` 응답은 다음 원인으로 나눠 처리한다.

- 고정 Quota 초과
- 공유 Capacity의 일시 부족
- Provisioned Throughput 초과 또는 잘못된 배포 호출
- Application이 자체 동시성 한도를 넘음

Client는 지수 Backoff와 Jitter, 최대 Retry 횟수, 전체 Deadline을 가진다. 생성 요청은 Retry 때 별도 과금과 서로 다른 결과가 발생할 수 있으므로 무제한 재시도하지 않는다. Application 앞단에 동시성 제한과 Token 기반 Admission Queue를 두면 Provider를 계속 Throttle하는 상황을 줄일 수 있다.

다른 Region으로 Failover할 때는 Model Version, 데이터 처리 규칙, Quota, Endpoint와 Safety 설정이 같은지 확인한다. Cross-Region Routing 기능을 사용해도 목적지 목록과 장애 범위를 기록한다.

### 6.5. Network 경로와 데이터 처리 경계

Private Endpoint는 Client에서 Cloud Service까지 Public Internet을 통과하지 않는 Network 경로를 제공한다. 이것만으로 Model 처리 Region, 데이터 보존 또는 학습 사용 정책이 결정되지는 않는다.

```text
Application VPC·VNet
        │ Identity + TLS
        v
Private Endpoint 또는 Public API
        │
        v
MaaS Front Door ──> 선택된 Model Runtime·Processing Region
        │                         │
        ├─ Safety·Abuse 처리      └─ 입력 처리와 출력 생성
        └─ Service Metric·Log
```

보안 검토에서는 다음 경계를 각각 확인한다.

1. DNS가 Private IP로 해석되고 실제 Packet이 Private 경로를 사용하는가?
2. Public Network Access를 차단할 수 있는가?
3. Prompt와 Response가 어느 Region 또는 Geography에서 처리되는가?
4. Request·Response, Uploaded File과 Fine-tuning Data가 저장되는가?
5. Abuse Monitoring 또는 Human Review를 위한 보존 예외가 있는가?
6. 입력이 Base Model 학습 또는 서비스 개선에 사용되는가?
7. Partner Model의 별도 약관과 Subprocessor가 적용되는가?
8. Application Log, APM과 Gateway가 Prompt 전체를 별도로 저장하는가?

AWS PrivateLink, Azure Private Link와 Google Cloud Private Service Connect 또는 VPC Service Controls는 이름과 적용 범위가 다르다. 해당 MaaS API, Region과 기능이 실제로 지원되는지 공식 Network Matrix에서 확인한다.

### 6.6. 사용량 기반 비용과 전용 처리 용량

Token 기반 MaaS의 월 비용은 다음과 같이 분해한다.

```text
월 MaaS 비용
= Σ(입력 Token × 입력 단가)
 + Σ(Cached 입력 Token × Cache 단가)
 + Σ(출력 Token × 출력 단가)
 + Image·Audio·Batch·Tool 등 별도 Meter
 + Network Egress, Log, Guardrail과 연계 서비스 비용
```

Provisioned Throughput는 다음과 같이 본다.

```text
월 Provisioned 비용
≈ Provisioned Unit 수 × Unit 시간 단가 × 청구 시간
 + 예약 범위를 넘긴 Spillover·Overage
 + 부가 서비스와 Network 비용
```

정확한 Meter는 Model과 Deployment Type마다 다르므로 Provider 가격표를 적용한다. `1M Token 단가`만 비교하면 다음 차이를 놓친다.

- Model별 Tokenizer와 같은 문장의 Token 수
- 입력과 출력 단가 차이
- Context Cache Hit와 Cache 저장 비용
- Retry, Timeout과 사용자가 취소한 Streaming 요청의 청구
- Tool Call, Grounding, Search와 Safety Service 비용
- Global·Regional·Batch·Priority 처리의 서로 다른 Meter

직접 Hosting과 비교할 때는 GPU 비용 외에 CPU, RAM, Storage, Network, Kubernetes Control Plane, Monitoring, 유휴 Replica와 운영 인력을 포함한다.

동일 품질과 SLO 조건에서 MaaS의 Token당 변동비와 직접 Hosting의 Token당 한계비용 차이가 양수라면 단순 손익분기 사용량은 다음과 같이 근사할 수 있다.

```text
손익분기 Token
≈ 직접 Hosting의 월 고정비
  ÷ (MaaS Token당 유효비용 - 직접 Hosting Token당 한계비용)
```

이 값은 Traffic이 일정하고 직접 Hosting 처리율이 충분할 때만 의미가 있다. Peak Capacity와 장애 여유 때문에 GPU가 유휴 상태라면 실제 손익분기는 더 커진다.

## 7. 제공 방식 선택

### 7.1. GPU VM과 Managed Kubernetes

| 조건 | GPU VM | Managed Kubernetes |
| --- | --- | --- |
| 단일 Model·단일 Host | 구성이 단순함 | Control Plane과 Add-on 부담이 큼 |
| 여러 Model·Team | Process와 Port 관리가 복잡해짐 | Namespace, Deployment와 Policy로 분리 가능 |
| Batch·Training Queue | 별도 Scheduler 필요 | Kubernetes Job 또는 별도 Batch Scheduler 연계 |
| Auto Scaling | VM·Process를 직접 연결 | Pod와 Node Scaling을 함께 구성 |
| GPU Driver | VM Image에서 직접 관리 | Node Image·Operator와 Upgrade 관리 |
| 장애 단위 | VM·Process | Pod·Node·Cluster Component |

Kubernetes는 GPU Capacity를 더 쉽게 확보하는 상품이 아니다. 여러 Workload의 배포, 격리와 Lifecycle 관리가 필요한지로 선택한다. 단일 Model Server 몇 개라면 VM과 Service Manager가 더 작은 운영 면적을 가질 수 있다.

### 7.2. Managed AI Compute와 직접 Serving

Managed AI Compute는 Endpoint 배포, Replica 교체, Metric과 Auto Scaling 일부를 Provider에 맡길 수 있다. 다음 조건에서는 검토 가치가 크다.

- 표준 Container 또는 지원 Model 형식으로 배포할 수 있다.
- Infra 운영보다 Model 배포·평가 주기를 줄이는 것이 중요하다.
- Provider IAM, Endpoint와 Monitoring에 통합해야 한다.
- Custom Scheduler와 특수 GPU Topology가 필요하지 않다.

직접 Serving은 다음 요구에 더 잘 맞을 수 있다.

- 특정 vLLM·TensorRT-LLM·SGLang Build와 Custom Kernel이 필요하다.
- GPU별 Memory 배치, Cache, Batching과 Parallelism을 직접 조정한다.
- 여러 Cloud 또는 On-premises에 같은 Runtime을 배포해야 한다.
- Managed Endpoint가 지원하지 않는 Model·License·Network 구성이 필요하다.

Managed Endpoint 비용에는 Provider가 관리하는 배포 계층이 포함될 수 있다. 같은 GPU 이름만 비교하지 말고 달성한 유효 Token/sec, SLO 통과 요청과 운영 비용을 함께 비교한다.

### 7.3. MaaS와 직접 Hosting

| 판단 기준 | MaaS | 직접 Hosting |
| --- | --- | --- |
| 시작 시간 | API Access 후 빠름 | Artifact·Runtime·Compute 배포 필요 |
| Model 선택 | Catalog와 Region에 제한 | License와 Runtime이 허용하는 Model |
| Weight 통제 | Provider가 관리 | 사용자가 Revision과 저장 위치 통제 |
| Runtime 최적화 | Provider 책임, 설정 범위 제한 | 사용자가 Kernel·Batch·Cache 조정 |
| 확장 | Rate Limit·Provisioned Unit | GPU Replica·Node 확장 |
| 비용 형태 | 사용량 또는 처리량 예약 | 실행 Compute와 운영비 |
| 데이터 경계 | Provider 정책·Deployment Type | 구성한 Network·Storage와 Runtime |
| Portability | API·Model별 차이 | Container·Artifact 이식 가능, Infra 차이 존재 |

MaaS는 작은 초기 Traffic, 빠른 Model 비교, Provider Model이 필요한 경우에 유리하다. 직접 Hosting은 Weight와 Runtime 통제, 높은 지속 사용률, 특정 데이터 경계 또는 Custom Model이 중요할 때 검토한다.

같은 Model Family 이름이어도 Provider별 Version, Quantization, Safety Layer와 API 기본값이 달라 출력과 성능이 같지 않을 수 있다. Application 추상화만으로 Model 동작 차이가 제거된다고 가정하지 않는다.

### 7.4. Control, Portability와 운영 책임

Control과 운영 책임은 함께 증가한다.

```text
Control 높음                                                   낮음
GPU VM ───────── Managed Kubernetes ───────── Managed Endpoint ───────── MaaS
OS·Driver·Runtime        Scheduler·Node             배포 설정             Model·API

운영 책임 큼                                                 작음
```

Portability는 `API가 비슷함`과 `동일 결과로 이동 가능함`을 구분한다. 이전 가능성을 판단할 때 다음 자산을 확인한다.

- Model Weight를 반출하거나 다른 Provider에서 합법적으로 사용할 수 있는가?
- Tokenizer, Chat Template와 Model Version을 고정할 수 있는가?
- Prompt, Tool Schema와 Structured Output가 다른 API에서 동작하는가?
- Fine-tuning Adapter, Evaluation Dataset과 Safety Policy를 이동할 수 있는가?
- Private Network, Identity와 Audit Log를 다시 구현할 수 있는가?

Multi-Cloud 추상화 계층은 인증과 기본 Request 형식을 통일할 수 있지만 Model Availability, Quota, Latency, 데이터 처리와 비용까지 통일하지는 않는다.

### 7.5. Cost, Latency와 Capacity 예측 가능성

선택안은 평균 비용 하나가 아니라 다음 세 축으로 평가한다.

| 축 | 측정값 |
| --- | --- |
| Cost | 월 고정비, 요청당 유효비용, 유휴율, Retry와 운영비 |
| Latency | p50·p95·p99 TTFT, TPOT, End-to-end와 Cold Start |
| Capacity | 최대 유효 Token/sec, Throttle율, Scale-out 시간과 장애 시 잔여량 |

작고 Burst가 큰 Traffic은 MaaS On-demand가 유휴 GPU 비용을 줄일 수 있다. 일정하고 큰 Traffic은 Provisioned Throughput 또는 직접 Hosting의 비용 예측 가능성이 높아질 수 있다. 하지만 손익분기점은 Model, Region, SLO와 실제 Utilization마다 달라진다.

비교 Load Test는 같은 Prompt 분포, 출력 상한, 동시성, Streaming 조건과 성공 판정 기준을 사용한다. 품질이 다른 Model의 Token 가격을 단순 비교하지 않는다.

## 8. 비교 및 확인 항목

### 8.1. Cloud별 동일 조건 비교표

세 Cloud의 제품은 완전히 같은 경계를 갖지 않는다. 다음 표는 기능 이름을 대응시키기 위한 출발점이며, 실제 지원 범위는 각 제품 문서에서 다시 확인한다.

| 계층·기능 | AWS | Microsoft Azure | Google Cloud |
| --- | --- | --- | --- |
| GPU IaaS | EC2 Accelerated Computing | Azure N-series VM | Compute Engine GPU Machine |
| Managed Kubernetes | EKS GPU Node | AKS GPU Node Pool | GKE GPU Node Pool |
| Managed Model Compute | SageMaker AI Endpoint | Azure ML Endpoint·Foundry Managed Compute | Vertex AI Endpoint |
| Foundation Model MaaS | Amazon Bedrock | Microsoft Foundry Models | Vertex AI Managed Models |
| 공유 처리량 | Bedrock On-demand | Standard 계열 Deployment | Pay-as-you-go·Dynamic Shared Quota |
| 전용 처리량 | Bedrock Provisioned Throughput | Provisioned Throughput Unit | Provisioned Throughput·GSU |
| VM Capacity 확보 | ODCR·지원 대상 Capacity Blocks | On-demand Capacity Reservation | Compute Engine Reservation |
| VM 비용 약정 | Savings Plans·Reserved Instance | Reservations·Savings Plan | Committed Use Discount |
| Interruptible VM | EC2 Spot | Azure Spot VM | Compute Engine Spot VM |
| Private 연결 | AWS PrivateLink VPC Endpoint | Azure Private Link | Private Service Connect 등 |

비교표에 실제 후보를 넣을 때는 각 Cloud에서 다음 조건을 동일하게 맞춘다.

- Model·Revision·Precision과 Runtime
- GPU당 VRAM, GPU 수와 내부·외부 연결
- vCPU, RAM, Local·Remote Storage와 Network
- Region·Zone, On-demand·Spot·Reservation 조건
- 최소 Replica, 장애 여유와 월 실행 시간
- p95/p99 SLO를 통과한 처리량
- Support, License, Logging와 Network 부가 비용

### 8.2. 배포 전 확인 절차

1. Workload를 고정한다.
   - Model·Version, 입력·출력 분포, 동시성, SLO와 월 사용량을 기록한다.
2. 제공 계층을 선택한다.
   - Weight·Runtime 통제가 필요한지, MaaS Catalog로 충분한지 판단한다.
3. Location과 데이터 경계를 확인한다.
   - Resource Region, 실제 처리 Geography, 저장·보존과 Partner 약관을 검토한다.
4. Compute 또는 처리량 후보를 산정한다.
   - GPU VRAM·수 또는 MaaS TPM·PTU·GSU 후보를 계산한다.
5. SKU·Model Availability와 Lifecycle을 확인한다.
   - Preview, Retirement와 지원 Deployment Type을 기록한다.
6. Quota를 확보한다.
   - GPU Family·Region Quota 또는 Model·Token·Provisioned Unit Quota를 요청한다.
7. 실제 Capacity를 검증한다.
   - VM·Node·Endpoint 생성 또는 Capacity Reservation 승인으로 확인한다.
8. IAM과 Network를 최소 권한으로 구성한다.
   - Workload Identity, Private DNS, Egress와 Public Access 차단을 시험한다.
9. Production 형태로 Load Test한다.
   - p95/p99 Latency, Token/sec, `429`, 오류율, Scale-out과 비용을 측정한다.
10. 장애와 변경을 시험한다.
    - Node 중단, Region Failover, Model Upgrade, Quota 소진과 Rollback을 검증한다.

VM 후보는 다음처럼 CLI로 현재 상태를 다시 조회한다. 출력 전체를 문서에 고정하지 말고 선택 근거와 조회 날짜만 저장한다.

```text
AWS   : EC2 Instance Type Offering + Service Quotas + 생성·Reservation 결과
Azure : Resource SKU Restrictions + VM Usage Quota + Capacity Reservation 결과
GCP   : Accelerator Type·Machine Type + Allocation Quota + Reservation 결과
```

MaaS는 최소·평균·Peak Traffic 세 구간을 시험한다. 다음 결과를 Provider별로 같은 단위로 정리한다.

| 결과 | 기록값 |
| --- | --- |
| 품질 | Task별 성공률, Golden Dataset Score, Safety 차단율 |
| Latency | TTFT, TPOT, End-to-end p50·p95·p99 |
| 처리량 | 성공 요청/초, 입력·출력 Token/초 |
| 제한 | `429` 비율, Retry 후 실패율, 최대 동시성 |
| 비용 | 성공 요청당 비용, 1K 출력 Token당 유효비용 |
| 복구 | Failover 시간, Scale-out 시간과 Version Rollback 시간 |

### 8.3. 변경 가능 정보와 확인 날짜

다음 정보는 설계 검토와 배포 직전에 다시 확인한다.

- GPU SKU, GPU Memory, Machine Type과 Network Specification
- Region·Zone Offering과 실제 Capacity
- Quota 기본값, 증액 가능 여부와 승인 Lead Time
- Spot 중단 조건, Reservation과 Commitment 상품
- Model ID·Version, Context와 Deployment Type
- MaaS 가격, Provisioned Unit 규칙과 Rate Limit
- Preview, GA, Deprecated와 Retirement 상태
- 데이터 처리 Region, 보존과 Network 지원 범위

선택 근거는 다음과 같은 짧은 Record로 남길 수 있다.

```yaml
checked_at: 2026-09-15
provider: <aws|azure|gcp>
service: <service-name>
offering: <instance-type|model-id-and-version>
region: <region>
zone: <zone-or-not-applicable>
purchase_or_deployment_type: <on-demand|spot|capacity-reservation|provisioned>
quota_name: <quota-name>
quota_value: <approved-value>
capacity_evidence: <reservation-id-or-test-result>
data_processing_scope: <regional|data-zone|global>
source_url: <official-document-url>
```

이 Record는 현재 상태의 증거이지 미래 Capacity 보장이 아니다. 장기 예약 ID와 계약 조건은 Asset Management System에서 관리하고, 공개 Repository에는 Account ID, Endpoint, Quota Ticket과 계약 가격을 노출하지 않는다.

## 9. References

아래 자료는 2026-09-15에 확인했다. SKU, Region, Model, Quota, Preview와 가격은 배포 직전에 각 Console과 공식 문서에서 다시 확인한다.

### 9.1. AWS

- [Specifications for Amazon EC2 accelerated computing instances](https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html)
- [Manage accelerated compute for AI/ML workloads on Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/ml-compute-management.html)
- [Best practices for deploying models on SageMaker AI Hosting Services](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-best-practices.html)
- [Making inference requests with Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/inference.html)
- [Quotas for the Bedrock Runtime endpoint](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-runtime.html)
- [Geographic cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html)
- [Reserve compute capacity with EC2 On-Demand Capacity Reservations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-capacity-reservations.html)
- [Best practices for Amazon EC2 Spot](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)
- [Use AWS PrivateLink to set up private access to Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html)

### 9.2. Microsoft Azure

- [NVIDIA CUDA on Azure overview](https://learn.microsoft.com/en-us/azure/virtual-machines/accelerator-technologies/cuda-overview)
- [Use GPUs for compute-intensive workloads on AKS](https://learn.microsoft.com/en-us/azure/aks/use-nvidia-gpu)
- [Deployment overview for Microsoft Foundry Models](https://learn.microsoft.com/en-us/azure/foundry/concepts/deployments-overview)
- [Microsoft Foundry architecture](https://learn.microsoft.com/en-us/azure/foundry/concepts/architecture)
- [Provisioned throughput for Foundry Models](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/provisioned-throughput)
- [Data, privacy, and security for Models sold by Azure](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy)
- [Check vCPU quotas](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas)
- [On-demand capacity reservation](https://learn.microsoft.com/en-us/azure/virtual-machines/capacity-reservation-overview)
- [Azure Spot Virtual Machines](https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms)
- [Configure network isolation for Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link)

### 9.3. Google Cloud

- [GPU machines in the accelerator-optimized machine family](https://cloud.google.com/compute/docs/accelerator-optimized-machines)
- [About GPU instances](https://cloud.google.com/compute/docs/gpus/about-gpus)
- [Run GPUs in GKE Standard node pools](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus)
- [Compute Engine allocation quotas](https://cloud.google.com/compute/resource-usage)
- [Compute Engine Spot VMs](https://cloud.google.com/compute/docs/instances/spot)
- [Reservations of Compute Engine zonal resources](https://cloud.google.com/compute/docs/instances/reservations-overview)
- [Throughput quota for Generative AI on Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/resources/throughput-quota)
- [Calculate Provisioned Throughput requirements](https://cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/measure-provisioned-throughput)
- [Vertex AI and zero data retention](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/vertex-ai-zero-data-retention)
