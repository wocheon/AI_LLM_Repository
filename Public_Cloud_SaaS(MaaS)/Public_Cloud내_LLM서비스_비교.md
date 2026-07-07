# Public Cloud 내 LLM 서비스 간 비교

## ✅ 클라우드 플랫폼별 지원 모델 목록

| 모델 종류 / 제공자            | **AWS Bedrock**                                       | **GCP Vertex AI**                                  | **Azure OpenAI**                     |
| ---------------------- | ----------------------------------------------------- | -------------------------------------------------- | ------------------------------------ |
| **OpenAI - GPT 계열**    | ❌ 미제공                                                 | ❌ 미제공                                              | ✅ GPT-4<br>✅ GPT-3.5<br>✅ Embeddings |
| **Anthropic - Claude** | ✅ Claude 3 Sonnet<br>✅ Claude 3 Haiku<br>✅ Claude 2.1 | ❌ (미지원)                                            | ❌ (미지원)                              |
| **Meta - Llama**       | ✅ Llama 3 8B<br>✅ Llama 3 70B                         | ❌ (직접 업로드 가능은 함)                                   | ❌ (미지원)                              |
| **Mistral**            | ✅ Mistral 7B<br>✅ Mixtral 8x7B                        | ❌ (직접 모델 업로드로 사용 가능)                               | ❌ (미지원)                              |
| **Amazon Titan**       | ✅ Titan Text G1<br>✅ Titan Embeddings                 | ❌ (GCP에서는 제공하지 않음)                                 | ❌ (미지원)                              |
| **Cohere**             | ✅ Command R<br>✅ Embed 모델                             | ❌ (GCP에서는 Cohere 모델 제공 안함)                         | ❌ (미지원)                              |
| **Google 모델**          | ❌ (Google 계열 모델 없음)                                   | ✅ Gemini 1.5 Pro / Flash<br>✅ PaLM 2<br>✅ Imagen 등 | ❌ (미지원)                              |
| **Custom 모델 업로드**      | ❌ 직접 업로드 불가                                           | ✅ 사용자 모델 업로드 및 배포 가능                               | ❌ 업로드 불가                             |


--- 

## ✅ 클라우드별 LLM 서비스 모델 비교

| 구분            | **AWS Bedrock**                            | **GCP Vertex AI**                     | **Azure OpenAI**                 |
| ------------- | ------------------------------------------ | ------------------------------------- | -------------------------------- |
| **서비스 유형**    | PaaS (Semi-Managed)                        | PaaS (Semi-Managed)                   | SaaS (Fully-Managed)             |
| **모델 배포**     | ❌ 직접 배포 없음<br>↪ AWS가 사전 배포한 모델 사용          | ✅ 모델 업로드 및 선택 가능<br>↪ 엔드포인트로 수동 배포 필요 | ✅ 모델 선택 후 바로 배포<br>↪ 이름만 정하면 끝   |
| **엔드포인트 제공**  | ❌ 자동 제공 안함<br>↪ Lambda + API Gateway 구성 필요 | ✅ API 엔드포인트 제공<br>↪ 모델 수동 연결 필요       | ✅ 자동으로 엔드포인트 제공                  |
| **API 호출 준비** | Lambda/SDK 구성 필요                           | SDK/REST API 간편                       | REST API 또는 SDK 간단 호출            |
| **인증 방식**     | IAM (SigV4)                                | OAuth2 / 서비스 계정                       | API Key                          |
| **주요 모델**     | Claude, Mistral, Titan, Llama 3 등          | PaLM2, Gemini, Custom models          | GPT-4, GPT-3.5, Codex, Embedding |

---

## 🔍 클라우드 전략 및 설계 철학 차이

| 항목         | **AWS**                                | **GCP**                         | **Azure**                         |
| ---------- | -------------------------------------- | ------------------------------- | --------------------------------- |
| **전략**     | 유연성과 제어권 중심 (Infra-first)              | ML 플랫폼 통합 전략 (ML 플랫폼 중심)        | SaaS-first 전략 (빠른 배포/접근)          |
| **서비스 철학** | 고객이 네트워크/보안/구성 자유도 갖게 함                | MLOps와 통합된 모델 수명주기 관리           | 엔터프라이즈 고객이 클릭 몇 번으로 사용 가능하도록 설계   |
| **보안/제어**  | IAM, VPC, PrivateLink 중심<br>고도화된 통제 제공 | 서비스 계정, VPC-SC<br>네트워크 수준 통제 가능 | API Key 기반<br>간편하지만 통제 수준은 낮음     |
| **대상 고객**  | 유연성과 고급 제어 원하는 엔지니어/개발자                | ML 전체 흐름을 다루는 데이터 과학자/ML 엔지니어   | Office, Azure AD 등 친숙한 엔터프라이즈 사용자 |

---

## 🧠 실무 선택 가이드

| 요구사항                          | 추천 서비스                                                  |
| ----------------------------- | ------------------------------------------------------- |
| 빠르게 LLM 서비스 시작                | ✅ **Azure OpenAI**                                      |
| ML 모델을 세밀하게 다루고 통합하고 싶음       | ✅ **GCP Vertex AI**                                     |
| 다양한 오픈소스 모델을 구성형태로 자유롭게 쓰고 싶음 | ✅ **AWS Bedrock**                                       |
| 사내망(VPC) 기반으로만 호출 가능하도록 하고 싶음 | ✅ **AWS + Private API Gateway** or GCP Private Endpoint |