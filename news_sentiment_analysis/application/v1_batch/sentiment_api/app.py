import re
from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
import torch
from transformers import AutoTokenizer, BertForSequenceClassification, ElectraForSequenceClassification
from typing import List, Dict
import configparser
import json
import asyncio
from openai import AsyncOpenAI  # [NEW] OpenAI SDK

# --- Config 로드 ---
config = configparser.ConfigParser()
config.read('config.ini')

# 로컬 모델 설정
KOBERT_MODEL_DIR = config.get('models', 'kobert_dir')
KOELECTRA_MODEL_DIR = config.get('models', 'koelectra_dir')

def load_label_map(section):
    return {int(k): v for k, v in config[section].items()}
KOBERT_LABEL_MAP = load_label_map('labels_kobert')
KOELECTRA_LABEL_MAP = load_label_map('labels_koelectra')

# LLM 설정
LLM_BASE_URL = config.get('llm', 'api_base')
LLM_API_KEY = config.get('llm', 'api_key', fallback="EMPTY")
LLM_MODEL_NAME = config.get('llm', 'model_name')
LLM_TIMEOUT = config.getint('llm', 'timeout', fallback=60)
LLM_LABELS = config.get('llm', 'sentiment_labels')
LLM_PROMPT = config.get('llm', 'prompt_template')
LLM_MAX_TOKENS = config.get('llm', 'max_tokens')

# 전역 리소스
ml_resources: Dict = {}

# [NEW] OpenAI 비동기 클라이언트 생성
# vLLM이나 Ollama 등 OpenAI 호환 서버라면 base_url만 맞추면 됨
aclient = AsyncOpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    timeout=LLM_TIMEOUT
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # (로컬 모델 로딩 로직은 기존과 동일)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Loading local models on {device}...")
    
    try:
        # KoBERT
        ml_resources["kobert_tokenizer"] = AutoTokenizer.from_pretrained(KOBERT_MODEL_DIR, trust_remote_code=True)
        ml_resources["kobert_model"] = BertForSequenceClassification.from_pretrained(KOBERT_MODEL_DIR).to(device)
        
        # KoELECTRA
        ml_resources["koelectra_tokenizer"] = AutoTokenizer.from_pretrained(KOELECTRA_MODEL_DIR, trust_remote_code=True)
        ml_resources["koelectra_model"] = ElectraForSequenceClassification.from_pretrained(KOELECTRA_MODEL_DIR).to(device)
        
        ml_resources["device"] = device
        print("✅ Local models loaded.")
    except Exception as e:
        print(f"❌ Error loading models: {e}")
        raise e

    yield
    ml_resources.clear()
    if torch.cuda.is_available(): torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan)

class BatchInputText(BaseModel):
    texts: List[str]

# --- 로컬 모델 추론 (기존 유지) ---
def predict_local_batch(tokenizer, model, label_map, texts, device):
    # ... (기존 코드와 동일: tokenizer -> model -> softmax -> argmax)
    inputs = tokenizer(texts, return_tensors="pt", truncation=True, max_length=256, padding=True).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)
        confidences, pred_labels = torch.max(probs, dim=1)
    
    results = []
    for i in range(len(texts)):
        idx = pred_labels[i].item()
        results.append({"sentiment": label_map.get(idx, str(idx)), "score": confidences[i].item()})
    return results

# --- [NEW] OpenAI SDK 기반 LLM 호출 ---
async def call_llm_single(text: str):
    prompt = LLM_PROMPT.format(text=text[:1000], labels=LLM_LABELS)
    
    try:
        response = await aclient.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                      {"role": "system", "content": "Return only a JSON object. Do not output thinking process."},
                      {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1024
        )
        content = response.choices[0].message.content
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        print(f"🔴 [LLM Raw Response]: {content}")
        
        # JSON 파싱
        clean = content.replace("``````", "").strip()
        parsed = json.loads(clean)
        if 'sentiment' in parsed:
            parsed['sentiment'] = parsed['sentiment'].lower()
        return parsed

    except Exception as e:
        print(f"LLM Error: {e}")
        return {"sentiment": "error", "score": 0.0, "msg": str(e)}

# --- 라우터 ---
@app.post("/predict/kobert/batch")
def kobert_batch(req: BatchInputText):
    res = predict_local_batch(ml_resources["kobert_tokenizer"], ml_resources["kobert_model"], KOBERT_LABEL_MAP, req.texts, ml_resources["device"])
    return {"model": "kobert", "count": len(res), "results": res}

@app.post("/predict/koelectra/batch")
def koelectra_batch(req: BatchInputText):
    res = predict_local_batch(ml_resources["koelectra_tokenizer"], ml_resources["koelectra_model"], KOELECTRA_LABEL_MAP, req.texts, ml_resources["device"])
    return {"model": "koelectra", "count": len(res), "results": res}

@app.post("/predict/llm/batch")
async def llm_batch(req: BatchInputText):
    # asyncio.gather로 병렬 호출
    tasks = [call_llm_single(text) for text in req.texts]
    results = await asyncio.gather(*tasks)
    return {"model": LLM_MODEL_NAME, "count": len(results), "results": results}


