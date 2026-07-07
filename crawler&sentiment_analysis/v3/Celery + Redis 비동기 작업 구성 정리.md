# Celery + Redis 기반 비동기 작업 구성 (FastAPI 예시)

## 0. 목적
- 목적: 긴 작업(LLM 라벨링, 대량 전처리, 모델 학습/평가, 배치 추론 등)을 API 요청-응답과 분리하여 비동기 처리한다.
- 핵심 요구사항:
  - 요청은 즉시 job_id 반환
  - 백그라운드에서 작업 수행
  - 상태 조회(queued/running/succeeded/failed) 및 결과 조회 제공
  - 재시도(retry) 및 장애 복구 고려

## 1. 구성 요소(Components)
- API 서버: FastAPI (job 생성/상태 조회)
- Message Broker(메시지 브로커): Redis
- Worker: Celery worker (작업 실행)
- Result Backend(결과 저장소): Redis 또는 다른 저장소(예: DB/S3)

Redis를 Celery의 broker로 쓰는 기본 설정은 `broker_url = redis://host:port/db` 형태를 사용한다. [web:119]  
Celery에서 Redis 결과 backend를 쓰려면 `result_backend = redis://...` 형태로 설정하며, redis extra 설치가 필요하다. [web:120]

## 2. 메시지 흐름(Flow)
1) Client → API: 작업 요청(예: dataset_labeling)
2) API → Redis(broker): Celery task enqueue
3) Worker → Redis(broker): task pop & execute
4) Worker → Redis(result backend): 결과/상태 저장
5) Client → API: job_id로 상태 조회


## 3. 운영 튜닝 포인트(Optimizations)
### 개념
- 긴 작업이 많을수록 worker가 “한 번에 너무 많은 task를 미리 가져가(prefetch)”서 큐가 비거나, 장애 시 재처리가 꼬일 수 있다.
- Celery 최적화 문서에서는 prefetch multiplier를 조정해 worker가 예약(reserve)하는 작업량을 줄이는 방식을 설명한다. [web:133]

### 실전 권장(예시)
- long-running task: `--prefetch-multiplier=1` 고려
- 멱등성(idempotency) 확보: 같은 job이 재시도되어도 결과가 망가지지 않게 설계
- 결과는 Redis에 오래 두지 말고(만료) 필요하면 S3/DB로 이동

## 4. 장단점 비교
### 장점
- API 응답 지연 감소(비동기)
- 워커 수평 확장(horizontal scaling) 용이
- 재시도/스케줄링/레이트리밋 등 task queue 장점을 활용 가능

### 단점
- 운영 복잡도 증가(브로커/워커/백엔드)
- 작업 멱등성/중복 실행/정확히 한 번(exactly-once) 처리에 대한 설계 부담
- Redis를 broker+backend로 같이 쓰면 리소스/키 관리(만료/용량/격리 DB index) 정책이 필요