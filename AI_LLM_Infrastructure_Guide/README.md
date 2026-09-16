# AI/LLM Infrastructure

관련 내용을 주제별 파일로 정리한다. 문서 사이에 정해진 읽기 순서는 없다.

- [01. AI Models](01_ai_models.md): AI 모델의 종류, NLU, 모델 구성요소, 활용 방식과 양자화
- [02. GPU System](02_gpu_system.md): GPU 하드웨어, 메모리, 연결 구조와 소프트웨어 Stack
- [03. GPU Execution Environment](03_gpu_execution_environment.md): GPU Host·Container 환경 구성, GPU Sharing, Kubernetes와 Slurm
- [04. Model Execution](04_model_execution.md): Model Download, Local 실행, GPU Serving, FastAPI Endpoint와 양자화 Model 실행
- [05. Infrastructure Sizing](05_infrastructure_sizing.md): VRAM, GPU, CPU, RAM, Storage와 Network 산정
- [06. Public Cloud GPU and MaaS](06_public_cloud_gpu_and_maas.md): AWS·Azure·GCP의 GPU 제공 방식, Capacity 확보와 MaaS
- [07. RAG and Model Training](07_rag_and_model_training.md): RAG 구성·운영, NLU·LLM Fine-tuning과 학습 Infrastructure
- [08. GPU Cluster Orchestration and Sharing](08_gpu_cluster_orchestration_and_sharing.md): vLLM·Ray, Slurm, Kubernetes Batch Scheduling과 GPU 공유 방식
