import configparser
import os
import torch
import numpy as np
import shutil
from datasets import load_dataset
from transformers.trainer_utils import get_last_checkpoint
from transformers import (
    ElectraTokenizer,
    ElectraForSequenceClassification,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding,
    TrainerCallback
)
from sklearn.metrics import accuracy_score, f1_score
import gc

# WANDB 비활성화 (로그인 요구 방지)
os.environ["WANDB_DISABLED"] = "true"
# 토크나이저 병렬 처리 경고 끄기
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ==========================================
# 0. 유틸리티 & 콜백 클래스
# ==========================================
def get_data_format(file_path):
    """파일 확장자를 기반으로 load_dataset의 포맷 파라미터를 결정"""
    ext = file_path.split('.')[-1].lower()
    if ext == 'csv': return 'csv'
    elif ext in ['json', 'jsonl']: return 'json'
    elif ext == 'parquet': return 'parquet'
    else:
        print(f"⚠ 알 수 없는 확장자(.{ext})입니다. 기본값 'csv'로 시도합니다.")
        return 'csv'

class DescriptionCallback(TrainerCallback):
    """학습 로그를 더 친절하게 출력하는 커스텀 콜백"""
    def on_log(self, args, state, control, logs=None, **kwargs):
        if state.is_local_process_zero and logs:
            epoch_info = f"[Epoch: {logs.get('epoch', 0):.2f}]"
            if 'loss' in logs:
                loss_val = logs['loss']
                if loss_val > 0.8: comment = "😰 아직 헤매는 중..."
                elif loss_val > 0.5: comment = "🤔 감을 잡는 중..."
                elif loss_val > 0.3: comment = "🙂 학습이 잘 되고 있어요!"
                else: comment = "🚀 완벽해요!"
                print(f"{epoch_info} Loss: {loss_val:.4f} -> {comment}")
            if 'learning_rate' in logs:
                print(f"   └─ LR: {logs['learning_rate']:.2e}")

# ==========================================
# 1. Config 로드
# ==========================================
config = configparser.ConfigParser()
config_path = 'config.ini'

if not os.path.exists(config_path):
    print(f"⚠ 경고: '{config_path}' 파일이 없습니다. 기본 설정을 사용합니다.")
    config['Path'] = {
        'model_name': 'klue/roberta-base',
        'train_file': 'dataset.csv',
        'output_dir': './output',
        'checkpoint_dir': './checkpoints'
    }
    config['Hyperparameters'] = {
        'num_labels': '3',
        'max_seq_length': '128',
        'batch_size': '64',
        'learning_rate': '2e-5',
        'epochs': '3',
        'seed': '42',
        'split_ratio': '0.2',
        'min_confidence': '0.8' # [New] 최소 신뢰도 설정
    }
else:
    config.read(config_path)

# [Path] 섹션 로드
MODEL_NAME = config['Path']['model_name']
TRAIN_FILE = os.path.abspath(config['Path']['train_file'])
VALID_FILE_RAW = config['Path'].get('valid_file', '').strip()
VALID_FILE = os.path.abspath(VALID_FILE_RAW) if VALID_FILE_RAW else ""
OUTPUT_DIR = config['Path']['output_dir']
CHECKPOINT_DIR = config['Path']['checkpoint_dir']

# [Hyperparameters] 섹션 로드
params = config['Hyperparameters']

NUM_LABELS = int(params.get('num_labels', 3))
MAX_LEN = int(params.get('max_seq_length', 128))
TARGET_BATCH_SIZE = int(params.get('batch_size', 64))
LR = float(params.get('learning_rate', 2e-5))
EPOCHS = int(params.get('epochs', 3))
SEED = int(params.get('seed', 42))
SPLIT_RATIO = float(params.get('split_ratio', 0.2))
MIN_CONFIDENCE = float(params.get('min_confidence', 0.8)) # [New] 필터링 기준

# [Subset] 옵션
USE_SUBSET = config.getboolean('Hyperparameters', 'use_subset', fallback=False)
SUBSET_SIZE = config.getint('Hyperparameters', 'subset_size', fallback=100)

print(f"▶ 모델: {MODEL_NAME}")
print(f"▶ 학습 파일: {TRAIN_FILE}")

# ==========================================
# 2. 데이터셋 로드 및 전처리 (수정됨)
# ==========================================
data_format = get_data_format(TRAIN_FILE)
print(f"▶ 감지된 포맷: {data_format}")

# 원본 데이터 로드
raw_dataset = load_dataset(data_format, data_files={"train": TRAIN_FILE})['train']

# -------------------------------------------------------------
# [Step A] 데이터 필터링 및 포맷팅
# -------------------------------------------------------------
def filter_and_format(example):
    # 1. Confidence 체크 (컬럼이 있는 경우만)
    if 'confidence' in example and example['confidence'] is not None:
        try:
            if float(example['confidence']) < MIN_CONFIDENCE:
                return False
        except:
            pass # 파싱 에러 시 안전하게 유지 혹은 제거(여기선 유지)
            
    # 2. Label 유효성 체크 (0, 1, 2만 허용)
    if example.get('label_sentiment') not in [0, 1, 2]:
        return False
        
    return True

print(f"📉 품질 필터링 전: {len(raw_dataset)}건")
filtered_dataset = raw_dataset.filter(filter_and_format)
print(f"📈 품질 필터링 후: {len(filtered_dataset)}건 (기준: conf >= {MIN_CONFIDENCE})")

# -------------------------------------------------------------
# [Step B] 입력 텍스트 조합 (테마 제외)
# -------------------------------------------------------------
def combine_text(example):
    tgt = example.get('target', '시장')
    # 테마(themes)는 추론 시 의존성 문제로 제외합니다.
    title = example.get('title', '')
    
    # [Target] Title 형식으로 결합
    combined_text = f"[{tgt}] {title}"
    
    return {
        "text": combined_text, 
        "label": int(example['label_sentiment']) 
    }

# 데이터 변환 적용 (기존 컬럼 제거)
processed_dataset = filtered_dataset.map(combine_text, remove_columns=filtered_dataset.column_names)

# 학습/검증 분할
if VALID_FILE and os.path.exists(VALID_FILE):
    # 검증 파일도 동일하게 전처리 필요
    raw_eval = load_dataset(data_format, data_files={"validation": VALID_FILE})['validation']
    eval_dataset = raw_eval.filter(filter_and_format).map(combine_text, remove_columns=raw_eval.column_names)
    train_dataset = processed_dataset
else:
    if len(processed_dataset) < 10:
        raise ValueError("❌ 데이터가 너무 적습니다. 최소 10개 이상 필요합니다.")
    split_datasets = processed_dataset.train_test_split(test_size=SPLIT_RATIO, seed=SEED)
    train_dataset = split_datasets["train"]
    eval_dataset = split_datasets["test"]

if USE_SUBSET:
    print(f"\n⚠ [테스트 모드] 데이터 축소 실행")
    if len(train_dataset) > SUBSET_SIZE:
        train_dataset = train_dataset.select(range(SUBSET_SIZE))
    eval_dataset = eval_dataset.select(range(min(len(eval_dataset), int(SUBSET_SIZE * 0.2))))

print(f"✅ 최종 준비 완료: 학습({len(train_dataset)}) / 검증({len(eval_dataset)})")
print(f"👀 입력 예시: {train_dataset[0]['text']} -> 라벨: {train_dataset[0]['label']}")

# ==========================================
# 3. 토크나이저 로드 및 패치
# ==========================================
print("⏳ 토크나이저 로드 중...")
tokenizer = ElectraTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

# [Monkey Patch] save_vocabulary 호환성 문제 해결
if not hasattr(tokenizer, "_original_save_vocabulary"):
    if hasattr(tokenizer, "save_vocabulary"):
        tokenizer._original_save_vocabulary = tokenizer.save_vocabulary

def patched_save_vocabulary(save_directory, filename_prefix=None):
    if hasattr(tokenizer, "_original_save_vocabulary"):
        return tokenizer._original_save_vocabulary(save_directory)
    else:
        return ()

tokenizer.save_vocabulary = patched_save_vocabulary

# 토크나이징 함수
def preprocess_function(examples):
    return tokenizer(
        examples["text"], 
        truncation=True, 
        padding="max_length", 
        max_length=MAX_LEN
    )

tokenized_train = train_dataset.map(preprocess_function, batched=True)
tokenized_eval = eval_dataset.map(preprocess_function, batched=True)

# ==========================================
# 4. 모델 및 학습 설정
# ==========================================
gc.collect()
torch.cuda.empty_cache()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"▶ 학습 장치: {device}")

model = ElectraForSequenceClassification.from_pretrained(
    MODEL_NAME, 
    num_labels=NUM_LABELS,
    trust_remote_code=True,
    ignore_mismatched_sizes=True
)
model.to(device)

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    acc = accuracy_score(labels, predictions)
    f1 = f1_score(labels, predictions, average="macro")
    return {"accuracy": acc, "f1": f1}

# OOM 방지 배치 사이즈 설정
SAFE_GPU_BATCH_SIZE = 4 
if TARGET_BATCH_SIZE < SAFE_GPU_BATCH_SIZE:
    calculated_accum_steps = 1
    real_batch_size = TARGET_BATCH_SIZE
else:
    calculated_accum_steps = TARGET_BATCH_SIZE // SAFE_GPU_BATCH_SIZE
    real_batch_size = SAFE_GPU_BATCH_SIZE

print(f"🔧 [설정] 목표 배치: {TARGET_BATCH_SIZE} -> 실제: {real_batch_size} (누적 {calculated_accum_steps}회)")

training_args = TrainingArguments(
    output_dir=CHECKPOINT_DIR,
    learning_rate=LR,
    per_device_train_batch_size=real_batch_size,
    per_device_eval_batch_size=real_batch_size,
    gradient_accumulation_steps=calculated_accum_steps,
    fp16=True,
    num_train_epochs=EPOCHS,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",    
    load_best_model_at_end=True,
    save_total_limit=2,
    seed=SEED,
    logging_dir=f"{OUTPUT_DIR}/logs",
    logging_steps=500,
    optim="adamw_torch"
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_eval,
    data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
    compute_metrics=compute_metrics,
    callbacks=[DescriptionCallback()],
)

# ==========================================
# 5. 학습 실행 및 저장
# ==========================================
print("🚀 학습 시작...")
last_checkpoint = get_last_checkpoint(CHECKPOINT_DIR) if os.path.isdir(CHECKPOINT_DIR) else None

trainer.train(resume_from_checkpoint=last_checkpoint)

print(f"💾 최종 모델 저장: {OUTPUT_DIR}")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print("🎉 완료!")