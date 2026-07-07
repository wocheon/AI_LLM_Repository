# Public Cloud SaaS (MaaS)

이 디렉토리에는 주요 퍼블릭 클라우드 서비스 제공업체(CSP)들이 제공하는 AI/ML 서비스(MaaS: Machine Learning as a Service)에 대한 자료를 정리합니다. 각 클라우드 벤더별로 제공하는 LLM 관련 서비스의 특징, 사용 방법, 예제 코드 등을 다룹니다.
# Public Cloud SaaS (MaaS)
## 목차

1.  **AWS (Amazon Web Services)**
    *   [Amazon Bedrock](AWS/Amazon_Bedrock.md)
    *   [Amazon SageMaker](AWS/Amazon_SageMaker.md)

2.  **Azure (Microsoft Azure)**
    *   [Azure OpenAI Service](Azure/Azure_OpenAI_Service.md)
    *   [Azure Machine Learning](Azure/Azure_Machine_Learning.md)

3.  **GCP (Google Cloud Platform)**
    *   [Vertex AI](GCP/Vertex_AI.md)
    *   [Google Cloud AI Platform](GCP/Google_Cloud_AI_Platform.md)

---

## 각 서비스별 개요

### 1. AWS (Amazon Web Services)

*   **Amazon Bedrock**:
    *   파운데이션 모델(FM)을 API 형태로 제공하는 완전 관리형 서비스입니다.
    *   Anthropic, AI21 Labs, Stability AI, Amazon 등 다양한 파트너사의 LLM을 쉽게 활용 가능합니다.
    *   RAG(Retrieval Augmented Generation), Agents for Bedrock, Fine-tuning 등 LLM 애플리케이션 개발에 필요한 도구들을 통합 제공합니다.
    *   자세한 내용은 [Amazon Bedrock 문서](AWS/Amazon_Bedrock.md)를 참조 바랍니다.

*   **Amazon SageMaker**:
    *   ML 모델의 구축, 학습, 배포 전 과정을 지원하는 완전 관리형 서비스입니다.
    *   LLM 학습 및 추론을 위한 인프라(GPU 인스턴스)와 도구(SageMaker JumpStart, SageMaker Endpoints)를 제공합니다.
    *   커스텀 LLM을 직접 학습시키거나 오픈 소스 LLM을 SageMaker 환경에서 배포할 때 주로 사용됩니다.
    *   자세한 내용은 [Amazon SageMaker 문서](AWS/Amazon_SageMaker.md)를 참조 바랍니다.

### 2. Azure (Microsoft Azure)

*   **Azure OpenAI Service**:
    *   OpenAI의 강력한 LLM(GPT-3, GPT-4, DALL-E 등)을 Azure의 보안, 규정 준수 및 엔터프라이즈 기능을 통해 제공하는 서비스입니다.
    *   Azure Private Link, VNet 통합 등을 통해 안전한 네트워크 환경에서 LLM을 사용 가능합니다.
    *   Fine-tuning, RAG 패턴 구현을 위한 Azure Cognitive Search와의 통합 등 다양한 엔터프라이즈 기능을 지원합니다.
    *   자세한 내용은 [Azure OpenAI Service 문서](Azure/Azure_OpenAI_Service.md)를 참조 바랍니다.

*   **Azure Machine Learning**:
    *   ML 모델의 라이프사이클 전반(데이터 준비, 모델 학습, 배포, 모니터링)을 관리하는 플랫폼입니다.
    *   LLM 학습 및 추론을 위한 컴퓨팅 리소스(GPU VM)와 MLOps 기능을 제공합니다.
    *   Azure OpenAI Service와 연동하여 커스텀 모델을 배포하거나, 오픈 소스 LLM을 자체 환경에 구축할 때 활용됩니다.
    *   자세한 내용은 [Azure Machine Learning 문서](Azure/Azure_Machine_Learning.md)를 참조 바랍니다.

### 3. GCP (Google Cloud Platform)

*   **Vertex AI**:
    *   Google Cloud의 통합 ML 플랫폼으로, 데이터 과학자와 ML 엔지니어가 ML 모델을 구축, 배포 및 관리할 수 있도록 지원합니다.
    *   PaLM, Gemini, Imagen 등 Google의 자체 LLM 및 파운데이션 모델을 API 형태로 제공하는 Vertex AI PaLM API (현재 Gemini API로 통합 중)를 포함합니다.
    *   AutoML, MLOps 도구, 노트북 환경(Workbench), 데이터 라벨링 서비스 등 ML 개발에 필요한 모든 기능을 한 곳에서 제공합니다.
    *   자세한 내용은 [Vertex AI 문서](GCP/Vertex_AI.md)를 참조 바랍니다.

*   **Google Cloud AI Platform**:
    *   (참고: Google Cloud AI Platform은 Vertex AI로 통합되면서 대부분의 기능이 Vertex AI로 이전되었습니다. 현재는 주로 레거시 워크로드 또는 특정 서비스에 한정적으로 사용될 수 있습니다.)
    *   이전에는 ML 모델 학습 및 배포를 위한 관리형 서비스를 제공했습니다.
    *   현재는 Vertex AI를 사용하는 것이 권장됩니다.
    *   자세한 내용은 [Google Cloud AI Platform 문서](GCP/Google_Cloud_AI_Platform.md)를 참조 바랍니다.
