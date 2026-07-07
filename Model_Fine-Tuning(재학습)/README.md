
# Model_FineTuninng (뉴스 감성분석 모델 재학습)

### 📌 개요
이 디렉토리는 한국어 뉴스 기사 분석에 최적화된 모델(`Kobert`, `DeBERTa V3`, `KoELECTRA` 등)을 파인튜닝(Fine-tuning)하고 관리하는 스크립트를 포함합니다.

### 📂 디렉토리 주요 파일
- **`kobert_train.py`** : **메인 학습 스크립트** (DeBERTa, BERT 계열 권장)
- **`koelectra_train.py`** : **KoELECTRA 전용 학습 스크립트** (토크나이저 및 모델 특성 고려하여 별도 관리)
- `compare_models.py` : 재학습 전/후 모델의 성능(Accuracy, F1-Score)을 비교
- `config.ini` : 학습 설정 파일 (경로, 하이퍼파라미터 등 공통 사용)
- `dataset_dir/` : 학습 데이터셋 디렉토리 (`csv`, `parquet`, `json` 지원)
- `logs/` : 학습 로그 저장소

### 🛠️ 요구사항 (Requirements)
- **OS:** Windows / Linux (Colab, Ubuntu 등)
- **Python:** 3.8+
- **Hardware:** NVIDIA GPU 권장 (VRAM 8GB 이상)
- **Libraries:**
  `pip install transformers datasets torch scikit-learn numpy tqdm`

### ⚙️ 설정 파일 (`config.ini`)
프로젝트 루트에 위치해야 하며, 학습할 모델과 파라미터를 정의합니다.

```ini
[Path]
# 1. DeBERTa/BERT 사용 시 (kobert_train.py 실행용)
model_name = team-lucid/deberta-v3-base-korean

# 2. KoELECTRA 사용 시 (koelectra_train.py 실행용 - 주석 해제 후 사용)
# model_name = monologg/koelectra-base-v3-discriminator

# 데이터 파일 (CSV, JSON, Parquet 지원)
train_file = ./dataset_dir/news_data.csv
valid_file =  ; 비워두면 train_file에서 자동 분할

# 결과 저장 경로
output_dir = ./models/fine_tuned_model
checkpoint_dir = ./checkpoints

[Hyperparameters]
num_labels = 3          ; 긍정/부정/중립 등 라벨 개수
max_seq_length = 128    ; 문장 최대 길이
batch_size = 64         ; 목표 배치 사이즈 (스크립트가 자동으로 GPU에 맞춰 최적화함)
learning_rate = 2e-5
epochs = 3
seed = 42
split_ratio = 0.2       ; 검증 데이터 비율 (20%)
```

### 🚀 사용법

#### 1) DeBERTa / KoBERT 학습
일반적인 BERT 계열이나 최신 DeBERTa 모델을 학습할 때 사용합니다.
```bash
python kobert_train.py
```
> **Tip:** 메모리 부족(OOM) 방지 기능이 내장되어 있어, `batch_size`를 64로 설정해도 GPU 메모리에 맞춰 자동으로 분할 처리(Gradient Accumulation)합니다.

#### 2) KoELECTRA 학습 (별도 실행)
KoELECTRA 모델을 사용할 때는 전용 스크립트를 사용하세요. `config.ini`의 모델명을 `monologg/koelectra-base-v3-discriminator` 등으로 변경해야 합니다.
```bash
python koelectra_train.py
```

#### 3) 모델 성능 비교
학습 전(Base Model)과 학습 후(Fine-tuned Model)의 성능 차이를 확인합니다.
```bash
python compare_models.py
```

### 💡 주요 기능 및 특징
1.  **자동 OOM 방지:** 고성능 모델(DeBERTa 등) 사용 시 빈번한 `CUDA Out of Memory` 에러를 방지하기 위해, 물리적 배치 사이즈를 자동으로 조절하고 Gradient Accumulation을 적용합니다.
2.  **다양한 포맷 지원:** `csv`, `json`, `parquet` 등 다양한 데이터 형식을 자동으로 감지하여 로드합니다.

### ⚠️ 주의사항
- **데이터 컬럼명:** 학습 데이터에는 텍스트 컬럼(예: `text`, `content`, `review`)과 라벨 컬럼(`label`)이 있어야 합니다.
- **DeBERTa V3 사용 시:** 학습 속도가 KoBERT보다 느릴 수 있으나, 뉴스 기사와 같은 문어체 분석 성능은 훨씬 뛰어납니다.
- **KoELECTRA 사용 시:** `model_name`에 반드시 `discriminator` 버전을 사용하세요. (Generator 사용 시 성능 저하)


## 참고 - 📊 모델 성능 지표 기준표 (Sentiment Analysis 기준)
| 상태           | Loss (손실)              | Accuracy (정확도)      | F1-Score   | 해석 및 조치                              |
| ------------ | ---------------------- | ------------------- | ---------- | ------------------------------------ |
| 초기화 / 학습 부족  | 0.9 ~ 1.5              | 33% ~ 50%           | 0.0 ~ 0.5  | 모델이 찍는 수준. 학습이 더 필요함. (Underfitting) |
| 학습 진행 중      | 0.6 ~ 0.8              | 60% ~ 75%           | 0.6 ~ 0.7  | 감을 잡기 시작함. Epoch를 더 돌려야 함.           |
| 사용 가능 (Good) | 0.4 ~ 0.5              | 80% ~ 88%           | 0.8 ~ 0.88 | 실전 배포 가능한 준수한 성능.                    |
| 최우수 (SOTA급)  | 0.1 ~ 0.3              | 90% 이상              | 0.9 이상     | 매우 훌륭함. 과적합(Overfitting) 주의 필요.      |
| 과적합 경고       | Train < 0.1Valid > 0.6 | Train 99%Valid 80%↓ | 격차 큼       | 암기왕 상태. 데이터 증강이나 조기 종료 필요.           |