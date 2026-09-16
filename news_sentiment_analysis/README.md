# News Sentiment Analysis

뉴스 기사 수집, 요약, 감성 분석 및 학습 데이터 구축 과정을 정리한 예제 모음입니다.

이 디렉터리는 하나의 애플리케이션을 `v1`부터 `v3`까지 순차적으로 교체한 구조가 아닙니다. 성격에 따라 다음 세 영역으로 구분합니다.

| 영역 | 목적 | 상태 |
| --- | --- | --- |
| [`application/v1_batch`](application/v1_batch/) | 수집 후 배치로 요약·감성 분석을 실행하는 초기 애플리케이션 | 학습·비교용 스냅샷 |
| [`application/v2_async`](application/v2_async/) | Redis와 Celery를 사용해 AI 작업을 비동기로 처리하는 애플리케이션 | v1의 개선판 |
| [`data_pipeline`](data_pipeline/) | 기사 수집, LLM 라벨링, 요약 및 임베딩을 수행하는 데이터 구축 파이프라인 | 별도 데이터 파이프라인 |
| [`archive`](archive/) | 초기 KoBERT·KoELECTRA 배치 구현 | 참고용 코드 |

## 전체 구조

```text
news_sentiment_analysis/
├── application/
│   ├── v1_batch/
│   └── v2_async/
├── data_pipeline/
│   ├── ingestion/
│   ├── enrichment/
│   ├── operations/
│   └── infrastructure/
├── docs/
└── archive/
```

## 애플리케이션 계보

### v1: 배치 처리

```text
기사 수집 → MariaDB/Elasticsearch 저장
         → 별도 요약 배치
         → 별도 감성 분석 배치
         → Flask 결과 조회
```

구현과 상세 아키텍처는 [`application/v1_batch/README.md`](application/v1_batch/README.md)를 참고합니다.

### v2: 비동기 처리

```text
기사 수집 → MariaDB/Elasticsearch 저장 → Redis 작업 등록
                                           ↓
                                    Celery Worker
                                      ├─ 기사 요약
                                      └─ 감성 분석
                                           ↓
                                    Flask 결과 조회
```

v1과 같은 서비스 범위를 유지하면서 Redis Queue와 Celery Worker를 도입한 버전입니다. 구현과 차이점은 [`application/v2_async/README.md`](application/v2_async/README.md)를 참고합니다.

## 데이터 파이프라인

기존 `v3` 코드는 애플리케이션의 다음 버전이 아니라 학습·검색용 뉴스 데이터를 만드는 파이프라인으로 분리했습니다.

```text
기사 수집/가져오기 → 본문 저장 → LLM 요약 → 타깃·테마·감성 라벨링 → 임베딩 생성
```

구성 및 실행 진입점은 [`data_pipeline/README.md`](data_pipeline/README.md)를 참고합니다.

관련 설계 문서:

- [`docs/dataset_pipeline.md`](docs/dataset_pipeline.md): 데이터셋 생성 원칙과 단계
- [`docs/model_training_serving.md`](docs/model_training_serving.md): 감성 분류 모델 학습·서빙 기준
- [`docs/celery_redis.md`](docs/celery_redis.md): Celery와 Redis 기반 비동기 작업 설계 참고

## 디렉터리 운영 원칙

- `application/v1_batch`와 `application/v2_async`는 아키텍처 변화 비교를 위해 독립된 스냅샷으로 유지합니다.
- 신규 데이터 수집·라벨링·임베딩 작업은 `data_pipeline`에 추가합니다.
- 더 이상 유지하지 않지만 참고 가치가 있는 코드는 `archive`에 보관합니다.
- 각 구성 요소의 `config.ini`는 해당 구성 요소 디렉터리를 기준으로 사용합니다. 실제 비밀정보는 저장소에 커밋하지 않고 환경변수나 로컬 설정으로 관리합니다.

