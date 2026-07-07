import os
import numpy as np
import evaluate
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    ElectraTokenizer,
    ElectraForSequenceClassification,
    Trainer,
    TrainingArguments
)

# ==========================================================
# 1. 설정
# ==========================================================
os.environ["WANDB_DISABLED"] = "true"

# 학습된 모델 경로
MODEL_PATH = "./models/fine_tunned_debert"
#MODEL_PATH = "./models/fine_tunned_kobert"
#MODEL_PATH = "./models/fine_tunned_koelectra"

# 검증용 데이터셋 경로 (단일 파일)
EVAL_DATA_PATH = "./dataset_dir/evaluate_dataset.csv"

# ==========================================================
# 2. 모델 및 토크나이저 로드
# ==========================================================

print(f"⏳ 모델 로드 중: {MODEL_PATH}")

# 모델 타입에 따른 클래스 자동 선택 로직
def get_model_classes(model_path):
    path_lower = model_path.lower()
    
    # 1. KoELECTRA인 경우
    if "koelectra" in path_lower:
        print(f"⚡ KoELECTRA 감지: Electra 전용 클래스를 사용합니다. ({model_path}), Class : ElectraTokenizer, ElectraForSequenceClassification")
        return ElectraTokenizer, ElectraForSequenceClassification
        
    # 2. 그 외 (DeBERTa, RoBERTa, KoBERT 등) -> Auto 클래스 사용
    else:
        print(f"🤖 일반 모델 감지: Auto 클래스를 사용합니다. ({model_path}), Class : AutoTokenizer, AutoModelForSequenceClassification")
        return AutoTokenizer, AutoModelForSequenceClassification

# 사용할 클래스 결정
TokenizerClass, ModelClass = get_model_classes(MODEL_PATH)

try:
    tokenizer = TokenizerClass.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = ModelClass.from_pretrained(MODEL_PATH)
except Exception as e:
    print(f"❌ 모델 로드 실패: {e}")
    exit(1)

# ==========================================================
# 3. 데이터 로드 및 전처리 (핵심 수정 구간)
# ==========================================================
print(f"📂 데이터 로드 중: {EVAL_DATA_PATH}")
dataset = load_dataset("csv", data_files=EVAL_DATA_PATH, split="train")

print(f"✅ 원본 데이터 개수: {len(dataset)}")

# ----------------------------------------------------------
# [중요] 학습 때와 동일한 입력 포맷 만들기
# 형식: [Target] Title
# ----------------------------------------------------------
def format_input(example):
    # None 값 방어 처리
    tgt = example.get('target')
    if tgt is None: tgt = '시장'
    
    title = example.get('title')
    if title is None: title = ''
    
    # 학습 코드의 combine_text 함수와 동일한 로직 적용
    # [핵심 변경] "[Target] Title" -> "Target 관련 뉴스: Title"
    combined_text = f"{tgt} 관련 뉴스: {title}"
    
    # 컬럼 매핑 (label_sentiment -> label)
    try:
        label = int(example['label_sentiment'])
    except (ValueError, TypeError):
        label = 0 # 에러 시 중립 처리

    return {
        "text": combined_text, 
        "label": label
    }

print("⚙️ 입력 포맷 변환 중 ([Target] Title)...")
formatted_dataset = dataset.map(format_input, remove_columns=dataset.column_names)

# ----------------------------------------------------------
# 토큰화 (Tokenization)
# ----------------------------------------------------------
def preprocess_function(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=128,
        padding="max_length"
    )

print("⚙️ 토큰화 진행 중...")
tokenized_dataset = formatted_dataset.map(preprocess_function, batched=True)

print(f"✅ 최종 평가 데이터 준비 완료: {len(tokenized_dataset)}개")
# print(f"👀 입력 예시: {tokenized_dataset[0]['text']} -> {tokenized_dataset[0]['label']}")

# ==========================================================
# 4. 평가 지표 정의
# ==========================================================
accuracy_metric = evaluate.load("accuracy")
f1_metric = evaluate.load("f1")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    accuracy = accuracy_metric.compute(predictions=predictions, references=labels)
    # average="macro": 클래스 불균형 고려 (0,1,2 골고루 잘 맞추는지)
    f1 = f1_metric.compute(predictions=predictions, references=labels, average="macro")

    return {
        "accuracy": accuracy["accuracy"],
        "f1": f1["f1"]
    }

# ==========================================================
# 5. 평가 실행
# ==========================================================
training_args = TrainingArguments(
    output_dir="./temp_eval_results",
    report_to="none",
    per_device_eval_batch_size=64,  # 평가 속도를 위해 크게 설정
    dataloader_num_workers=4        # 데이터 로딩 속도 향상
)

trainer = Trainer(
    model=model,
    args=training_args,
    eval_dataset=tokenized_dataset,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics
)

print("🚀 평가 시작...")
metrics = trainer.evaluate()

print("\n📊 최종 평가 성적표:")
print("=" * 30)
for key, value in metrics.items():
    if "eval_" in key:
        key = key.replace("eval_", "")
    print(f"{key}: {value:.4f}")
print("=" * 30)
