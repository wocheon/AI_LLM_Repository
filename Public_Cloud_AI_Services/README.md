# Public Cloud AI Services

AWS, Microsoft Azure, Google Cloud가 제공하는 AI 인프라와 관리형 모델 서비스를 비교하고, 서비스별 호출 예제를 정리한다.

이 디렉터리에서 `MaaS`는 **Model as a Service**를 뜻한다. 다만 GPU VM과 자체 모델 배포처럼 MaaS보다 넓은 범위도 다루므로, 디렉터리 이름에는 포괄적인 `AI Services`를 사용한다.

## 구성

- [퍼블릭 클라우드 생성형 AI 모델 서비스 비교](Public_Cloud내_LLM서비스_비교.md)
- [퍼블릭 클라우드 VM 및 GPU 아키텍처 비교](Public_cloud별_VM_및_GPU아키텍쳐_비교.md)
- `AWS_Bedrock/`: Amazon Bedrock 호출 및 모델 조회 예제
- `Azure_OpenAI/`: Azure OpenAI 호출 예제
- `GCP_VertexAI/`: Vertex AI 및 OpenAI 호환 API 호출 예제

## 문서 사용 시 주의사항

모델, 리전, 할당량, 가격, 지원 API와 서비스 명칭은 자주 변경된다. 실제 도입 시에는 각 문서에 연결된 공식 모델 카탈로그와 리전별 지원표를 다시 확인한다.
