import configparser
import os
import torch
import numpy as np
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments
)
from sklearn.metrics import accuracy_score, f1_score, classification_report

# ==========================================
# 1. 설정 로드
# ==========================================
config = configparser.ConfigParser()
config.read('config.ini')

ORIGINAL_MODEL = config['Path']['model_name']           # 원본 모델
FINETUNED_MODEL = config['Path']['output_dir']          # 재학습된 모델 (./my_finetuned_model)
TRAIN_FILE = os.path.abspath(config['Path']['train_file'])
VALID_FILE_RAW = config['Path'].get('valid_file', '').strip()
VALID_FILE = os.path.abspath(VALID_FILE_RAW) if VALID_FILE_RAW else ""

NUM_LABELS = config.getint('Hyperparameters', 'num_labels')
MAX_LEN = config.getint('Hyperparameters', 'max_seq_length')
BATCH_SIZE = config.getint('Hyperparameters', 'batch_size') * 2  # 평가니까 배치를 좀 늘려도 됨

# ==========================================
# 2. 검증 데이터 준비 (train.py와 동일 로직)
# ==========================================
print("⏳ 데이터셋 로드 중...")
if VALID_FILE and os.path.exists(VALID_FILE):
    dataset = load_dataset("parquet", data_files={"validation": VALID_FILE})
    eval_dataset = dataset["validation"]
else:
    raw_dataset = load_dataset("parquet", data_files={"train": TRAIN_FILE})
    # 시드 고정하여 동일하게 분할
    split_datasets = raw_dataset["train"].train_test_split(test_size=config.getfloat('Hyperparameters', 'split_ratio'), seed=config.getint('Hyperparameters', 'seed'))
    eval_dataset = split_datasets["test"]

# 테스트 모드라면 데이터 축소 (빠른 결과 확인용)
USE_SUBSET = config.getboolean('Hyperparameters', 'use_subset', fallback=False)
if USE_SUBSET:
    eval_subset_size = max(int(config.getint('Hyperparameters', 'subset_size', fallback=100) * 0.2), 20)
    if len(eval_dataset) > eval_subset_size:
        eval_dataset = eval_dataset.select(range(eval_subset_size))
        print(f"⚠ [테스트 모드] 검증 데이터 {len(eval_dataset)}개로 축소됨")

# 전처리
tokenizer = AutoTokenizer.from_pretrained(ORIGINAL_MODEL)
def preprocess_function(examples):
    return tokenizer(examples["Review_Text"], truncation=True, padding="max_length", max_length=MAX_LEN)

tokenized_eval = eval_dataset.map(preprocess_function, batched=True)
if "Label" in tokenized_eval.column_names:
    tokenized_eval = tokenized_eval.rename_column("Label", "label")

# ==========================================
# 3. 평가 함수 정의
# ==========================================
def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    acc = accuracy_score(labels, predictions)
    f1 = f1_score(labels, predictions, average="macro")
    return {"accuracy": acc, "f1": f1}

def evaluate_model(model_path, model_desc):
    print(f"\n🔍 [{model_desc}] 평가 시작... ({model_path})")
    try:
        model = AutoModelForSequenceClassification.from_pretrained(model_path, num_labels=NUM_LABELS)
    except OSError:
        print(f"❌ 모델을 찾을 수 없습니다: {model_path}")
        return None

    # Trainer를 평가용으로만 사용
    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir="./temp_logs", per_device_eval_batch_size=BATCH_SIZE, dataloader_pin_memory=False),
        eval_dataset=tokenized_eval,
        compute_metrics=compute_metrics
    )

    result = trainer.evaluate()
    print(f"   👉 Accuracy: {result['eval_accuracy']:.4f}")
    print(f"   👉 F1 Score: {result['eval_f1']:.4f}")
    return result

# ==========================================
# 4. 비교 실행
# ==========================================
print("\n" + "="*50)
print("📊 모델 성능 비교 리포트")
print("="*50)

res_orig = evaluate_model(ORIGINAL_MODEL, "원본 모델 (Base)")
res_fine = evaluate_model(FINETUNED_MODEL, "재학습 모델 (Fine-tuned)")

if res_orig and res_fine:
    acc_diff = res_fine['eval_accuracy'] - res_orig['eval_accuracy']
    f1_diff = res_fine['eval_f1'] - res_orig['eval_f1']

    print("\n" + "="*50)
    print("📈 최종 결과 요약")
    print("="*50)
    print(f"정확도 변화: {res_orig['eval_accuracy']:.4f} -> {res_fine['eval_accuracy']:.4f} ({'+' if acc_diff>0 else ''}{acc_diff:.4f})")
    print(f"F1 점수 변화: {res_orig['eval_f1']:.4f} -> {res_fine['eval_f1']:.4f} ({'+' if f1_diff>0 else ''}{f1_diff:.4f})")

    if acc_diff > 0:
        print("🎉 성능이 향상되었습니다!")
    else:
        print("🤔 성능이 떨어졌거나 비슷합니다. 데이터나 하이퍼파라미터를 점검해보세요.")
