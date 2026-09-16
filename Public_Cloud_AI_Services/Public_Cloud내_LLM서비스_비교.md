# 퍼블릭 클라우드 생성형 AI 모델 서비스 비교

> 최종 확인일: 2026-09-16
>
> 비교 대상: Amazon Bedrock, Microsoft Foundry Models, Google Cloud Vertex AI

이 문서는 각 클라우드의 **관리형 생성형 AI 모델 호출**, **예약 처리량**, **사용자 모델 배포** 방식을 비교한다. 모델 버전과 제공 리전은 자주 바뀌므로 고정된 모델 목록보다 서비스 구조와 선택 기준을 중심으로 설명한다.

## 1. 용어와 비교 범위

- 이 문서에서 `MaaS`는 **Model as a Service**를 뜻한다. 사용자는 모델 서버와 GPU를 직접 운영하지 않고 관리형 API로 모델을 호출한다.
- 세 서비스 모두 관리형 API, 배포 제어면, 보안 및 거버넌스 기능을 함께 제공한다. 따라서 한 서비스를 `SaaS`, 다른 서비스를 `PaaS`로 단순 분류하는 방식은 사용하지 않는다.
- `모델 카탈로그에 존재함`, `현재 프로젝트와 리전에서 호출 가능함`, `특정 API와 기능을 지원함`은 서로 다른 조건이다.
- 아래의 모델 제공사 예시는 전체 목록이 아니다. 실제 사용 가능 여부는 공식 카탈로그와 리전별 지원표를 기준으로 판단한다.

## 2. 서비스 포지션 요약

| 구분 | Amazon Bedrock | Microsoft Foundry Models | Google Cloud Vertex AI |
|---|---|---|---|
| 기본 포지션 | AWS의 관리형 파운데이션 모델 및 생성형 AI 플랫폼 | Azure의 통합 모델 카탈로그·배포·AI 애플리케이션 플랫폼 | Google Cloud의 통합 AI/ML 플랫폼과 생성형 AI 서비스 |
| 대표적인 자사 모델 | Amazon Nova, Titan 계열 | Microsoft Phi·MAI 계열 및 Azure에서 제공하는 OpenAI 모델 | Gemini, Imagen, Veo 계열 |
| 대표적인 외부 모델 제공사 | Anthropic, Meta, Mistral AI, Cohere, AI21 Labs 등 | OpenAI, Anthropic, Meta, Mistral AI, Cohere 등 | Anthropic, Meta, Mistral AI 및 여러 오픈 모델 등 |
| 완전 관리형 호출 | On-demand 및 Cross-Region Inference | Serverless API의 Standard 계열 배포 | Gemini API 및 지원 모델의 MaaS |
| 예약 처리량 | Provisioned Throughput | Provisioned 배포(PTU) | Provisioned Throughput(GSU) |
| 사용자 모델 경로 | 지원 아키텍처에 대한 Custom Model Import 및 일부 모델 미세 조정 | Managed compute를 통한 오픈·파트너·사용자 모델 배포 | Model Garden, 사전 제작 또는 사용자 컨테이너를 이용한 Endpoint 배포 |
| 강한 생태계 결합 | IAM, CloudTrail, CloudWatch, PrivateLink, Bedrock Guardrails·Agents·Knowledge Bases | Microsoft Entra ID, Azure RBAC·Policy, Private Link, Foundry 프로젝트·에이전트·평가 | Google Cloud IAM, VPC Service Controls, Vertex AI 학습·평가·파이프라인·Model Garden |

`Azure OpenAI Service`는 여전히 사용할 수 있지만, Azure의 전체 모델 선택과 배포 방식을 비교할 때는 OpenAI 모델뿐 아니라 타사·오픈 모델까지 포괄하는 **Microsoft Foundry Models**가 더 적절한 비교 단위다.

## 3. 모델 제공 및 배포 방식

### 3.1. Amazon Bedrock

Bedrock은 AWS와 여러 모델 제공사의 파운데이션 모델을 관리형 런타임 API로 제공한다.

- 기본 호출은 `bedrock-runtime` 엔드포인트를 사용하며 별도의 Lambda 또는 API Gateway가 필수는 아니다.
- `Converse`는 여러 지원 모델을 공통 메시지 형식으로 호출할 때 사용한다.
- `InvokeModel`은 모델별 요청·응답 형식과 세부 기능을 직접 제어할 때 사용한다.
- 모델에 따라 OpenAI 호환 `Responses`, `Chat Completions` 또는 Anthropic `Messages` 형식을 사용할 수 있다.
- On-demand 용량 외에 지리적 또는 전역 Cross-Region Inference와 Provisioned Throughput을 선택할 수 있다. 두 기능의 지원 모델과 결합 가능 여부는 별도로 확인해야 한다.
- Custom Model Import는 지원되는 모델 아키텍처와 리전에서 사용할 수 있으며, 모든 Bedrock 기능이 가져온 모델에 동일하게 적용되는 것은 아니다.

### 3.2. Microsoft Foundry Models

Microsoft Foundry Models는 Azure OpenAI 모델과 Microsoft·파트너·커뮤니티 모델을 하나의 카탈로그와 배포 체계에서 다룬다.

- Serverless API는 토큰 기반 Standard, 예약 용량 기반 Provisioned, 비동기 Batch 등의 배포 형식을 제공한다.
- 데이터 처리 범위에 따라 Global, Data Zone, Regional 계열을 선택한다. 모든 모델이 모든 배포 형식과 리전을 지원하지는 않는다.
- 지원 모델은 OpenAI 호환 SDK와 REST API를 사용할 수 있지만, 세부 API와 기능 호환성은 모델별로 확인해야 한다.
- Managed compute는 오픈 모델이나 사용자 모델을 관리형 전용 GPU 용량에 배포하는 경로다. 문서 확인일 기준 일부 기능은 Preview다.
- Instant access는 일부 모델을 명시적 배포 없이 호출하는 기능이며, 문서 확인일 기준 Preview다.

### 3.3. Google Cloud Vertex AI

Vertex AI는 Google 모델의 관리형 API와 Model Garden의 파트너·오픈 모델, 사용자 모델 배포를 함께 제공한다.

- Gemini API는 Vertex AI 프로젝트와 리전을 지정해 Google Gen AI SDK 또는 REST API로 호출한다.
- 지원되는 파트너·오픈 모델의 MaaS는 GPU 인프라를 직접 프로비저닝하지 않고 관리형 API로 호출한다.
- 같은 모델이라도 MaaS용 모델 카드와 자체 배포용 모델 카드가 나뉠 수 있다.
- 자체 또는 커스텀 가중치가 필요하면 Model Garden의 사전 제작 컨테이너나 사용자 컨테이너를 Vertex AI Endpoint에 배포할 수 있다.
- 일정한 처리량이 필요한 지원 모델은 GSU 단위의 Provisioned Throughput을 검토한다.

## 4. 호출 및 운영 특성 비교

| 항목 | Amazon Bedrock | Microsoft Foundry Models | Google Cloud Vertex AI |
|---|---|---|---|
| 기본 호출 단위 | 모델 ID 또는 Inference Profile | Foundry 리소스의 모델 Deployment | 프로젝트·리전·모델 ID 또는 배포된 Endpoint |
| 주요 API | Converse, InvokeModel, Responses, Chat Completions, Messages | 모델별 Responses 또는 Chat Completions 등 OpenAI 호환 API와 Foundry SDK | `generateContent` 계열, Google Gen AI SDK, 모델별 REST·호환 API |
| 기본 인증 | IAM 자격 증명과 SigV4 | Microsoft Entra ID 또는 API Key | Google Cloud IAM과 ADC, 지원 구성의 API Key |
| 운영 환경 권장 인증 | IAM Role과 단기 자격 증명 | Managed Identity·Service Principal과 Entra ID RBAC | Service Account·Workload Identity·Federation과 ADC |
| 간편 개발용 인증 | Bedrock API Key 지원 | API Key 지원 | API Key 또는 사용자 ADC 지원 |
| 사설 연결 | VPC Interface Endpoint와 AWS PrivateLink | Private Endpoint와 Azure Private Link | 기능별 Private Endpoint·Private Service Connect, VPC Service Controls |
| 종량 처리 | On-demand, 지원 모델의 Cross-Region Inference | Standard 계열의 토큰 기반 과금 | Pay-as-you-go 또는 Dynamic Shared Quota 계열 |
| 예약 처리량 | 모델별 Provisioned Throughput | PTU 기반 Provisioned 배포 | GSU 기반 Provisioned Throughput |
| 직접 호스팅에 가까운 경로 | Custom Model Import | Managed compute | Vertex AI Endpoint에 자체 배포 |
| 관측·감사 | CloudWatch, CloudTrail | Azure Monitor, 활동 로그와 Foundry 관측 기능 | Cloud Monitoring, Cloud Logging, Audit Logs |

### 인증 관련 주의사항

- API Key를 소스 코드나 저장소에 넣지 않는다.
- Bedrock의 장기 API Key는 탐색 용도로 제한하고, 운영 환경에서는 IAM Role 또는 단기 자격 증명을 우선한다.
- Azure 운영 환경은 Microsoft Entra ID 기반의 키 없는 인증을 우선 검토한다.
- Google Cloud 운영 환경은 서비스 계정 키 파일을 장기 보관하기보다 Workload Identity 또는 Federation과 ADC를 우선 검토한다.

## 5. 네트워크와 데이터 처리 위치

사설 연결 기능이 있다는 사실만으로 모든 모델 호출이 특정 리전 안에서 처리된다고 간주하면 안 된다.

| 확인 항목 | 점검 내용 |
|---|---|
| 요청 진입 경로 | Public endpoint인지 PrivateLink·Private Endpoint·PSC 경로인지 확인 |
| 실제 추론 위치 | Global, Cross-Region, Data Zone 또는 단일 리전 중 어디에서 처리되는지 확인 |
| 저장 위치 | 로그, 캐시, Batch 입출력, 미세 조정 데이터와 안전성 처리 데이터의 저장 위치 확인 |
| 조직 경계 | AWS Organizations SCP, Azure Policy, GCP Organization Policy·VPC-SC 적용 범위 확인 |
| 기능별 예외 | Grounding, 웹 검색, Agent 도구, 외부 데이터 연결이 별도 네트워크 경로를 사용하는지 확인 |

- Bedrock Cross-Region Inference는 Inference Profile이 허용하는 리전으로 요청을 라우팅한다. 지리적 프로필과 전역 프로필의 경계를 구분한다.
- Foundry의 Global, Data Zone, Regional 배포는 추론 데이터가 처리될 수 있는 범위가 다르다.
- Vertex AI의 VPC-SC, Private Endpoint와 PSC 지원 여부는 모델, API, 배포 방식별로 다를 수 있다.

## 6. 비용과 용량 계획

단순한 입력·출력 토큰 단가만으로 서비스를 비교하지 않는다.

1. 평균 및 최대 입력·출력 토큰 수
2. 초당 요청 수, 동시 요청 수와 허용 지연시간
3. Prompt caching, Batch, Grounding, 도구 호출 등 부가 비용
4. On-demand 할당량과 Rate Limit 증설 가능성
5. 예약 처리량의 최소 단위, 약정 기간과 미사용 용량 비용
6. 자체 모델 배포 시 GPU·Endpoint 가동 시간, 최소 Replica와 오토스케일링 비용
7. Cross-Region 또는 Global 처리 사용 시 데이터 경계와 가격 차이

예약 처리량 단위는 서로 직접 환산되지 않는다. Bedrock의 모델 단위 Provisioned Throughput, Foundry의 PTU, Vertex AI의 GSU는 각 공급자의 모델·버전·배포 위치와 처리량 계산 방식에 따라 별도로 산정한다.

## 7. 실무 선택 가이드

| 우선 요구사항 | 우선 검토할 서비스 | 이유와 추가 확인 사항 |
|---|---|---|
| AWS IAM·VPC·감사 체계와 빠른 통합 | Amazon Bedrock | AWS 운영 체계와 자연스럽게 결합된다. 대상 모델의 리전과 Converse 지원 여부를 확인한다. |
| OpenAI 모델과 Azure 엔터프라이즈 통제 | Microsoft Foundry Models | Entra ID, Azure RBAC·Policy 및 다양한 데이터 처리 범위를 활용할 수 있다. 필요한 모델의 배포 유형을 확인한다. |
| Gemini와 Google Cloud 데이터·ML 플랫폼 통합 | Vertex AI | Gemini API와 Vertex AI의 학습·평가·파이프라인을 함께 사용할 수 있다. 리전과 Quota를 확인한다. |
| 여러 모델 제공사를 동일 클라우드에서 비교 | 세 서비스 모두 | 카탈로그 수보다 실제 리전, API 기능, 모델 수명주기와 계약 조건을 비교한다. |
| 사용자 가중치와 런타임 제어 | 각 서비스의 자체 배포 경로 | Bedrock Custom Model Import, Foundry Managed compute, Vertex AI Endpoint의 지원 범위와 운영 책임이 서로 다르다. |
| 엄격한 단일 리전 데이터 처리 | 세 서비스 모두 개별 검증 | Global·Cross-Region 기본값을 피하고 해당 모델의 Regional 제공 여부와 부가 기능의 데이터 흐름을 확인한다. |
| 높은 고정 트래픽과 예측 가능한 지연시간 | Provisioned 또는 자체 배포 비교 | PTU·GSU·Provisioned Throughput과 GPU 직접 배포의 총비용을 실제 부하 시험으로 비교한다. |

특정 서비스가 항상 더 간단하거나 더 안전하다고 일반화하기 어렵다. 이미 사용하는 클라우드의 ID·네트워크·감사 체계, 필요한 모델, 데이터 처리 위치와 운영 역량을 함께 평가해야 한다.

## 8. 도입 전 체크리스트

- [ ] 필요한 모델과 정확한 버전이 대상 리전에 있는가?
- [ ] Streaming, Tool calling, Structured output, Embedding, Multimodal 등 필요한 API 기능을 지원하는가?
- [ ] Preview 기능을 운영 의존성으로 사용해도 되는가?
- [ ] On-demand와 예약 처리량의 Quota 및 증설 절차를 확인했는가?
- [ ] 입력·출력 데이터, 로그와 캐시의 저장 및 처리 위치를 확인했는가?
- [ ] Workload Identity 기반 인증과 최소 권한 정책을 적용했는가?
- [ ] Public access 차단 후 필요한 사설 경로와 DNS가 실제로 동작하는가?
- [ ] 모델 버전 폐기와 자동 업그레이드 정책에 대응할 수 있는가?
- [ ] 동일한 평가 데이터와 부하 조건으로 품질·지연시간·비용을 측정했는가?
- [ ] 공급자 장애와 모델 Capacity 부족에 대한 Fallback 전략이 있는가?

## 9. 공식 문서

### AWS

- [Amazon Bedrock 모델 가용성 및 API 호환성](https://docs.aws.amazon.com/bedrock/latest/userguide/models.html)
- [Amazon Bedrock 지원 API](https://docs.aws.amazon.com/bedrock/latest/userguide/apis.html)
- [Custom Model Import](https://docs.aws.amazon.com/bedrock/latest/userguide/model-customization-import-model.html)
- [Amazon Bedrock API Key](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html)
- [Amazon VPC와 AWS PrivateLink로 Bedrock 데이터 보호](https://docs.aws.amazon.com/bedrock/latest/userguide/usingVPC.html)
- [Cross-Region Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)

### Microsoft Azure

- [Microsoft Foundry 개요](https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry)
- [Microsoft Foundry Models 배포 개요](https://learn.microsoft.com/en-us/azure/foundry/concepts/deployments-overview)
- [Microsoft Entra ID 기반 키 없는 인증](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/configure-entra-id)
- [Microsoft Foundry Private Link 구성](https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link)
- [Foundry Models 수명주기 및 지원 정책](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements)

### Google Cloud

- [Generative AI on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs)
- [Gemini API in Vertex AI 빠른 시작](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart)
- [Vertex AI에서 오픈 모델 MaaS 사용](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/open-models/use-maas)
- [Vertex AI 생성형 AI 보안 제어](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/security-controls)
- [Vertex AI Provisioned Throughput 산정](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/measure-provisioned-throughput)
- [Vertex AI Online Inference Private Endpoint](https://docs.cloud.google.com/vertex-ai/docs/predictions/using-private-endpoints)
