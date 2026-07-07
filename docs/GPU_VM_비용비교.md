

## Public Cloud 별 서울리전에서 사용가능 GPU 모델

### AWS 서울 리전 (ap-northeast-2)

| GPU 모델           | 대표 인스턴스                 | 상태                   |
| ---------------- | ----------------------- | -------------------- |
| NVIDIA H100 80GB | p5시리즈                   | 미출시                  |
| NVIDIA A100 40GB | p4d.24xlarge            | 사용 가능                |
| NVIDIA A10G 24GB | g5시리즈                   | 사용 가능                |
| NVIDIA L4 24GB   | g6.xlarge ~ g6.48xlarge | 제공 중 (2025년 하반기 추가됨) |
| NVIDIA T4 16GB   | g4dn시리즈                 | 사용 가능                |


### GCP 서울 리전 (asia-northeast3)

| GPU 모델           | 대표 머신 타입                    | 상태                  |
| ---------------- | --------------------------- | ------------------- |
| NVIDIA H100 80GB | a3-highgpu                  | 미제공                 |
| NVIDIA A100 40GB | a2-highgpu시리즈               | 사용 가능               |
| NVIDIA L4 24GB   | g2-standard/n2-standard+ L4 | 제공 중 (2024년 말부터 가용) |
| NVIDIA T4 16GB   | n1/n2-standard+ T4          | 사용 가능               |
| NVIDIA A10G      | 미제공                         |                     |


### Microsoft Azure 서울 리전 (Korea Central / Korea South)
| GPU 모델           | 대표 VM 시리즈        | 상태                         |
| ---------------- | ---------------- | -------------------------- |
| NVIDIA H100 80GB | ND_H100_v5       | 미출시                        |
| NVIDIA A100 80GB | ND96amsr_A100_v4 | 사용 가능                      |
| NVIDIA A10 24GB  | NVads_A10_v5     | 사용 가능                      |
| NVIDIA L4 24GB   | NVLads_L4_v5     | 한국 리전은 미제공 (미국, 싱가포르부터 시작) |
| NVIDIA T4 16GB   | NCas_T4_v3       | 사용 가능                      |

<br>

---

<br>


## Public Cloud 별 GPU 인스턴스 주요 사양 및 가격 비교
| 벤더사   | 리전                 | 인스턴스 이름 / 머신 타입           | GPU 모델           | GPU 수 | vCPU | 메모리(GB) | 추정 네트워크(Gbps) | 월 요금 (KRW)   |
| ----- | ------------------ | ------------------------- | ---------------- | ----- | ---- | ------- | ------------- | ------------ |
| AWS   | ap-northeast-2     | p4d.24xlarge              | NVIDIA A100 40GB | 8     | 96   | 1152    | 최대 400        | 약 32,961,360 |
| AWS   | ap-northeast-2     | p4de.24xlarge             | NVIDIA A100 80GB | 8     | 96   | 1152    | 최대 400        | 약 35,280,000 |
| AWS   | ap-northeast-2     | g6.xlarge                 | NVIDIA L4 24GB   | 1     | 4    | 16      | 최대 10         | 약 2,822,400  |
| AWS   | ap-northeast-2     | g6.4xlarge                | NVIDIA L4 24GB   | 1     | 16   | 64      | 최대 15         | 약 3,225,600  |
| AWS   | ap-northeast-2     | g6.12xlarge               | NVIDIA L4 24GB   | 1     | 48   | 192     | 최대 25         | 약 3,801,600  |
| AWS   | ap-northeast-2     | g5.12xlarge               | NVIDIA A10G 24GB | 1     | 48   | 192     | 최대 25         | 약 3,547,680  |
| AWS   | ap-northeast-2     | g5.24xlarge               | NVIDIA A10G 24GB | 4     | 96   | 384     | 최대 50         | 약 13,497,600 |
| AWS   | ap-northeast-2     | g4dn.xlarge               | NVIDIA T4 16GB   | 1     | 4    | 16      | 최대 25         | 약 532,176    |
| AWS   | ap-northeast-2     | g4dn.12xlarge             | NVIDIA T4 16GB   | 4     | 48   | 192     | 최대 100        | 약 2,116,800  |
| GCP   | asia-northeast3    | a2-highgpu-1g             | NVIDIA A100 40GB | 1     | 12   | 85      | 최대 100        | 약 3,931,200  |
| GCP   | asia-northeast3    | a2-highgpu-2g             | NVIDIA A100 40GB | 2     | 24   | 170     | 최대 100        | 약 7,862,400  |
| GCP   | asia-northeast3    | a2-highgpu-4g             | NVIDIA A100 40GB | 4     | 48   | 340     | 최대 100        | 약 15,724,800 |
| GCP   | asia-northeast3    | a2-highgpu-8g             | NVIDIA A100 40GB | 8     | 96   | 680     | 최대 100        | 약 31,449,600 |
| GCP   | asia-northeast3    | a2-megagpu-16g            | NVIDIA A100 40GB | 16    | 96   | 1360    | 최대 100        | 약 79,632,000 |
| GCP   | asia-northeast3    | g2-standard-4             | NVIDIA L4 24GB   | 1     | 4    | 16      | 최대 16         | 약 2,318,400  |
| GCP   | asia-northeast3    | g2-standard-8             | NVIDIA L4 24GB   | 1     | 8    | 32      | 최대 16         | 약 2,620,800  |
| GCP   | asia-northeast3    | g2-standard-16            | NVIDIA L4 24GB   | 2     | 16   | 64      | 최대 32         | 약 5,241,600  |
| GCP   | asia-northeast3    | g2-standard-32            | NVIDIA L4 24GB   | 4     | 32   | 128     | 최대 64         | 약 10,483,200 |
| GCP   | asia-northeast3    | n1-standard-8 + 1xT4      | NVIDIA T4 16GB   | 1     | 8    | 30      | 최대 32         | 약 620,160    |
| GCP   | asia-northeast3    | n1-standard-8 + 2xT4      | NVIDIA T4 16GB   | 2     | 8    | 30      | 최대 32         | 약 1,240,320  |
| GCP   | asia-northeast3    | n1-standard-8 + 4xT4      | NVIDIA T4 16GB   | 4     | 8    | 30      | 최대 32         | 약 2,480,640  |
| Azure | korea-central      | Standard_ND96amsr_A100_v4 | NVIDIA A100 80GB | 8     | 96   | 1900    | 최대 400        | 약 32,256,000 |
| Azure | korea-central      | Standard_ND40rs_v2        | NVIDIA V100 32GB | 8     | 40   | 672     | 최대 200        | 약 24,192,000 |
| Azure | korea-central      | Standard_NVads_A10_v5     | NVIDIA A10 24GB  | 1     | 12   | 110     | 최대 25         | 약 2,620,800  |
| Azure | korea-central      | Standard_NC4as_T4_v3      | NVIDIA T4 16GB   | 1     | 4    | 28      | 최대 25         | 약 513,720    |
| Azure | korea-central      | Standard_NC8as_T4_v3      | NVIDIA T4 16GB   | 2     | 8    | 56      | 최대 50         | 약 1,027,440  |
| Azure | korea-central      | Standard_NC64as_T4_v3     | NVIDIA T4 16GB   | 8     | 64   | 448     | 최대 100        | 약 4,109,760  |
| Azure | korea-central (예정) | Standard_NVLads_L4_v5     | NVIDIA L4 24GB   | 1     | 12   | 110     | 최대 25         | 약 2,016,000  |