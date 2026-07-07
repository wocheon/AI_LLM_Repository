# 데이터셋 생성 파이프라인 템플릿 (수집 → LLM 라벨링 → confidence → 밸런싱 → 중복 제거)

## 0. 목표/원칙
- 목표: 3-class 감성분류(Positive/Neutral/Negative)에 적합한 고품질 뉴스 텍스트 데이터셋을 구축한다.
- 원칙:
  - 재현 가능(Repeatable): 동일 조건이면 동일 결과가 나와야 함(Seed, 버전 고정)
  - 추적 가능(Traceable): 각 row의 출처/라벨링 프롬프트/모델/결과를 역추적 가능해야 함
  - 누수 방지(No leakage): Train/Valid/Test 간 문장 중복/유사 중복을 엄격히 방지

## 1. 데이터 스키마(권장)
- raw 단계(수집 직후)
  - `id` (UUID)
  - `source` (예: naver, dart, press, rss 등)
  - `published_at` (ISO8601)
  - `url`
  - `target` (entity/ticker/theme; 없으면 null)
  - `title`
  - `body` (optional)
  - `lang`
  - `hash_exact` (정규화 후 SHA256)
  - `ingested_at`

- labeled 단계(라벨링 이후)
  - `text_input` (학습 입력 포맷: `{target} 관련 뉴스: {title}` 등)
  - `label_sentiment` (0/1/2)
  - `confidence` (0.0~1.0)
  - `llm_model` (예: gpt-4.1-mini 등)
  - `llm_prompt_version`
  - `llm_reason_short` (optional, 짧게)
  - `labeled_at`

## 2. 수집(Collect)
### 개념
- 다양한 소스에서 원천 데이터를 수집하고, 정규화(normalization) 후 저장한다.

### 예시(정규화 규칙)
- 공백 통일: 연속 공백 1개로 축약
- 특수문자 표준화(따옴표, 대시 등)
- URL 파라미터 제거(가능하면 canonical)

### 장단점
- 장점: 소스 다양성은 일반화 성능을 올린다.
- 단점: 소스마다 문체/노이즈가 달라 전처리 정책이 필요.

## 3. LLM 라벨링(Labeling)
### 개념
- LLM에게 “감성 라벨 + confidence”를 동시에 출력하게 해서, 후처리에서 품질을 자동으로 제어한다.

### 프롬프트 템플릿 예시
- 입력: target, title(필요 시 body 일부)
- 출력(JSON 강제):
  - `label_sentiment`: 0/1/2
  - `confidence`: 0~1
  - `rationale_short`: 1~2문장(선택)

### 장단점
- 장점: 대규모 라벨링 속도/비용 최적화 가능
- 단점: 라벨 일관성(Consistency)을 위해 prompt/version 관리가 필수

## 4. confidence 산출(Confidence)
### 개념
- confidence는 “정답 가능성이 높은 데이터만 학습에 쓰기 위한 품질 지표”다.
- confidence를 높게 걸면 성능이 좋아질 수 있지만, 데이터가 줄어 학습이 불안정해질 수 있다.

### 운영 가이드
- Train 생성: `confidence >= 0.90` (고순도 학습)
- Valid/Test 생성: `confidence >= 0.95` 또는 사람이 검수한 gold set 권장

## 5. 밸런싱(Balancing)
### 개념
- 3-class에서 라벨 불균형은 “중립만 찍는 모델”을 만들기 쉽다.
- 따라서 학습셋은 라벨별 목표 개수로 맞춘다(예: Positive/Neutral/Negative 각각 N개).

### 예시 정책
- `min(count_pos, count_neu, count_neg)` 기준으로 언더샘플링(Undersampling)
- 또는 부족 라벨은 추가 수집/추가 라벨링(권장)

### 장단점
- 장점: macro F1 개선
- 단점: 언더샘플링은 데이터 일부를 버리므로, 가능하면 “부족 라벨을 더 모으는 방식”이 좋음

## 6. 중복 제거(Dedup)
### 개념
- 완전 중복(exact dup) + 유사 중복(near dup)을 제거해야 Train/Valid/Test 누수를 막는다.

### 구현 정책(권장)
- exact dedup:
  - normalize(title) → `hash_exact`로 그룹핑 → 1개만 남김
- near dedup(선택):
  - MinHash/SimHash/embedding cosine similarity로 유사도 임계치 기반 제거
  - 동일 날짜/동일 타깃에서 거의 동일 제목이 반복되는 케이스 방지

## 7. 스플릿(Split)
### 개념
- 랜덤 split만 하면 같은 이슈(사건) 관련 문장이 Train/Valid에 동시에 들어갈 수 있다.
- 뉴스 도메인은 “시간 기반 split(time-based split)” 또는 “이슈/URL 기반 그룹 split”을 권장.

### 예시
- 최근 2주치 데이터를 Test로 홀드아웃(hold-out)
- 나머지는 Train/Valid로 분리