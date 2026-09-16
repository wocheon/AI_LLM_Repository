# AI 모델 실행 방식

Model 실행은 파일을 내려받는 작업, RAM·VRAM에 적재하는 작업, 요청을 받는 Server를 여는 작업으로 나뉜다. 같은 Model이라도 실행 Runtime에 따라 지원 형식, 필요한 Memory, API, 동시 처리 방식이 달라진다.

이 문서는 Model Artifact를 직접 보유하고 Local PC 또는 GPU Server에서 실행하는 방법을 다룬다. GPU Driver와 Container Runtime 구성은 [GPU 실행 환경](03_gpu_execution_environment.md), Public Cloud의 Managed Model API는 [Public Cloud GPU와 MaaS](06_public_cloud_gpu_and_maas.md)에서 별도로 다룬다.

## 1. Model Artifact 확보

### 1.1. 실행 대상 확인

Model 이름만 보고 파일을 받으면 실행 단계에서 형식이나 Runtime이 맞지 않는 경우가 많다. Download 전에 다음 항목을 먼저 확인한다.

| 확인 항목 | 확인할 내용 | 실행 환경에 미치는 영향 |
|---|---|---|
| Task | Text Classification, Embedding, Causal LM, Vision-Language 등 | Loader Class와 API Schema가 달라진다. |
| Architecture | Encoder, Decoder, Encoder-Decoder, MoE 등 | Runtime 지원 여부와 VRAM 사용 방식이 달라진다. |
| Weight 형식 | Safetensors, PyTorch Checkpoint, GGUF, GPTQ, AWQ 등 | 사용할 수 있는 Runtime이 제한된다. |
| Precision | FP32, FP16, BF16, INT8, INT4 등 | 파일 크기와 RAM·VRAM 요구량이 달라진다. |
| Tokenizer | Vocabulary, Special Token, Chat Template 포함 여부 | 누락되거나 다른 Version이면 입력과 출력이 달라질 수 있다. |
| License·Access | 사용 범위, 상업 이용, Gated Model 승인 | 자동 배포와 Artifact 복제 가능 여부에 영향을 준다. |
| Custom Code | `trust_remote_code` 필요 여부 | 외부 Python Code 실행에 대한 검토가 필요하다. |

Hugging Face Model Repository에는 일반적으로 다음 파일이 포함된다. 모든 Model이 같은 파일 구성을 갖는 것은 아니다.

```text
model-directory/
├── config.json
├── model.safetensors
│   또는 model-00001-of-0000N.safetensors
├── model.safetensors.index.json
├── tokenizer.json
├── tokenizer_config.json
├── special_tokens_map.json
├── generation_config.json
└── README.md
```

`config.json`은 Architecture와 주요 설정을, Weight 파일은 학습된 Parameter를, Tokenizer 파일은 Text를 Token ID로 변환하는 규칙을 가진다. Chat Model은 `tokenizer_config.json` 등에 Chat Template이 포함될 수 있다.

### 1.2. Hugging Face Hub에서 Local로 Download

`from_pretrained()`에 Repository ID를 직접 전달하면 필요한 파일을 실행 시점에 Cache로 받는다. 빠른 시험에는 편리하지만, 운영 환경에서는 Model 시작 시간이 Network 상태에 의존하고 실행할 Revision도 변할 수 있다. 배포 전에 Model을 명시적인 경로로 받아 두는 편이 재현과 장애 분석에 유리하다.

다음 예시는 전체 Model Repository를 특정 Commit 기준으로 받는다.

```bash
python -m pip install --upgrade huggingface_hub

MODEL_ID=organization/model-name
MODEL_REVISION=full-commit-hash
MODEL_DIR=/srv/models/model-name

hf download "$MODEL_ID" \
  --revision "$MODEL_REVISION" \
  --local-dir "$MODEL_DIR"
```

Gated 또는 Private Model은 `HF_TOKEN`을 Process 환경이나 Secret Store로 주입한다. Token을 Script, Container Image 또는 Git Repository에 기록하지 않는다.

Python에서 동일한 작업을 수행할 수 있다.

```python
import os

from huggingface_hub import snapshot_download

snapshot_download(
    repo_id=os.environ["MODEL_ID"],
    revision=os.environ["MODEL_REVISION"],
    local_dir=os.environ["MODEL_DIR"],
    token=os.getenv("HF_TOKEN"),
)
```

Branch나 Tag는 나중에 다른 Commit을 가리킬 수 있다. 동일 Artifact를 다시 배포해야 한다면 전체 Commit Hash를 기록한다. 필요한 형식이 명확할 때는 `allow_patterns`와 `ignore_patterns`로 불필요한 Framework Weight를 제외할 수 있지만, Config나 Tokenizer까지 제외하지 않도록 주의한다.

### 1.3. Cache와 명시적 Model Directory

| 방식 | 적합한 경우 | 주의점 |
|---|---|---|
| Hugging Face Cache | 개발 환경에서 여러 Revision과 Model을 반복 시험 | Cache Snapshot과 실제 Commit을 함께 확인해야 한다. |
| 명시적 Local Directory | 운영 배포, Offline 실행, Read-only Volume 배포 | Artifact Version과 Directory 수명주기를 직접 관리해야 한다. |
| Container Image에 포함 | 작고 변경이 드문 Model | Image가 커지고 Build·배포 시간이 증가한다. |
| Object Storage에서 시작 시 복제 | 여러 Node가 같은 Artifact를 사용 | Cold Start, 동시 Download와 Storage Traffic을 제어해야 한다. |

운영 Container에서는 Model을 Image에 매번 복사하기보다 Version이 고정된 Volume을 Read-only로 Mount하는 구성이 관리하기 쉽다. 환경에 따라 Image와 Artifact를 하나의 불변 배포 단위로 묶는 편이 더 적절할 수도 있다.

### 1.4. Hub Download와 Hosted Inference API

Hugging Face Hub는 Model Artifact 저장소다. `hf download`나 `from_pretrained()`는 파일을 현재 환경으로 가져오며, 이후 Compute와 Serving은 사용자가 관리한다.

Hugging Face Inference Providers 같은 Hosted API는 외부 Provider가 Model을 실행하고 Network API로 결과를 돌려준다. Local GPU는 필요하지 않지만 Model Version, Region, Rate Limit, 데이터 처리 경계와 비용을 확인해야 한다. Repository가 존재한다고 해서 해당 Model에 Hosted Inference Endpoint가 항상 제공되는 것은 아니다.

### 1.5. Artifact 검증

실행 전에 다음 정보를 배포 기록에 남긴다.

1. Repository ID와 전체 Commit Hash
2. Weight 형식, Precision과 Quantization 방식
3. Model·Tokenizer Config 및 Chat Template 유무
4. License와 Gated Model 승인 조건
5. 지원 Runtime 및 검증한 Runtime Version
6. Artifact 전체 크기와 필요한 Local Disk 여유 공간
7. `trust_remote_code=True` 사용 여부와 검토한 Code Revision

가능하면 Safetensors 형식을 우선 검토한다. Pickle 기반 Checkpoint는 역직렬화 과정의 Code 실행 위험을 별도로 다뤄야 한다. `trust_remote_code=True`가 필요한 Model은 Repository의 Python Code가 현재 Process에서 실행되므로 작성자와 Code를 검토하고 Commit Hash를 고정한다.

## 2. Transformers를 사용한 직접 실행

### 2.1. 실행 흐름

Transformers를 직접 사용하면 전처리, Device 배치, Batch와 후처리를 Application Code에서 제어할 수 있다. NLU Model이나 단일 Process 실험에는 단순하지만, 다수 사용자의 생성 요청을 효율적으로 Scheduling하는 기능은 별도 Serving Runtime보다 제한적이다.

```text
Model Directory
  ├─ Config ────────────────┐
  ├─ Weight ──> RAM ──> VRAM├─> Forward Pass ─> Output Tensor
  └─ Tokenizer ─> CPU Tensor┘                         │
                                   Label Mapping 또는 Text Decode
```

PyTorch 설치는 GPU Driver와 지원 CUDA Runtime 조합에 맞춰야 한다. 환경 구성과 검증 방법은 [GPU 실행 환경](03_gpu_execution_environment.md)을 따른다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install transformers accelerate safetensors
```

위 명령은 Transformers 관련 Package만 보여준다. `torch`는 PyTorch 공식 설치 Selector에서 현재 OS와 Accelerator에 맞는 명령을 확인하여 별도로 설치한다. 운영 환경에서는 검증한 Package Version을 Lock File로 고정한다.

### 2.2. NLU Text Classification 실행

다음 예시는 Fine-tuning된 Sequence Classification Model을 Local Directory에서 불러와 Batch 추론한다.

```python
import os

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = os.environ.get("MODEL_PATH", "/srv/models/text-classifier")
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForSequenceClassification.from_pretrained(
    model_path,
    local_files_only=True,
).to(device)
model.eval()

texts = ["배송이 빨라서 만족합니다.", "결제가 계속 실패합니다."]
inputs = tokenizer(
    texts,
    padding=True,
    truncation=True,
    max_length=256,
    return_tensors="pt",
).to(device)

with torch.inference_mode():
    logits = model(**inputs).logits
    probabilities = torch.softmax(logits, dim=-1)

scores, label_ids = probabilities.max(dim=-1)
for text, label_id, score in zip(texts, label_ids.tolist(), scores.tolist()):
    label = model.config.id2label.get(label_id, str(label_id))
    print({"text": text, "label": label, "score": score})
```

Tokenization은 주로 CPU와 RAM을 사용하고, 입력 Tensor와 Weight를 GPU로 옮긴 뒤 Forward Pass가 수행된다. Batch를 키우면 GPU 활용률이 높아질 수 있지만 입력 Tensor와 Activation Memory도 증가한다. `max_length`는 Application 입력 정책과 Model이 학습된 조건을 함께 고려해 정한다.

### 2.3. Causal LM 실행

다음 예시는 하나의 GPU 또는 CPU에서 Causal LM을 직접 실행하는 최소 흐름이다.

```python
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path = os.environ.get("MODEL_PATH", "/srv/models/instruct-model")
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

if device.type == "cuda":
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
else:
    dtype = torch.float32

tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    dtype=dtype,
    low_cpu_mem_usage=True,
    local_files_only=True,
).to(device)
model.eval()

messages = [{"role": "user", "content": "GPU와 VRAM의 차이를 두 문장으로 설명해줘."}]
prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)
inputs = tokenizer(prompt, return_tensors="pt").to(device)

with torch.inference_mode():
    output_ids = model.generate(
        **inputs,
        max_new_tokens=128,
        do_sample=False,
    )

generated_ids = output_ids[0, inputs.input_ids.shape[1]:]
print(tokenizer.decode(generated_ids, skip_special_tokens=True))
```

Chat Template이 없는 Base Model에는 이 예제를 그대로 적용할 수 없다. Model Card에서 입력 형식을 확인한다. `device_map="auto"`는 여러 GPU와 CPU·Disk Offload를 빠르게 시험할 때 편리하지만 배치 위치와 성능을 자동 결정에 맡긴다. 운영 Serving에서는 실제 배치 결과와 통신 경로를 확인한 뒤 명시적인 전략을 사용한다.

### 2.4. Device와 dtype 확인

```python
print("device:", next(model.parameters()).device)
print("dtype:", next(model.parameters()).dtype)
print("memory footprint:", model.get_memory_footprint())

if torch.cuda.is_available():
    print("allocated:", torch.cuda.memory_allocated())
    print("reserved:", torch.cuda.memory_reserved())
```

`memory_allocated()`와 `memory_reserved()`는 같은 값이 아니다. PyTorch Allocator가 재사용하려고 예약한 Memory가 포함되므로 `nvidia-smi`의 Process 사용량과도 차이가 날 수 있다.

### 2.5. 직접 실행의 적합 범위

Transformers 직접 실행이 적합한 경우는 다음과 같다.

- 전처리와 후처리가 중요한 NLU·Embedding·Vision Model
- Offline Batch 작업과 단일 사용자 기능 시험
- Custom Layer 또는 Model Code 검증
- Serving Runtime 지원 전 Architecture 검증

생성형 Model에 다수의 동시 요청이 들어오면 Request Queue, Continuous Batching, KV Cache, Streaming, Timeout과 Metric을 Application에서 직접 구현해야 한다. 이 경우 vLLM 같은 Serving Runtime을 먼저 검토한다.

## 3. Local 실행 도구

### 3.1. 도구별 위치

| 도구 | 주된 실행 형태 | 대표 Artifact | 적합한 용도 |
|---|---|---|---|
| Ollama | CLI와 Local Daemon | Registry Model, GGUF, 지원되는 Safetensors Model·Adapter | 빠른 Local 실행과 Application 연동 |
| llama.cpp | Native Binary 또는 Container | GGUF | CPU·GPU Offload를 직접 조정하는 경량 실행 |
| LM Studio | Desktop GUI와 `lms` CLI | 지원되는 Local Model 형식 | GUI 기반 Model 탐색, Memory 설정과 API 시험 |
| Docker Model Runner | Docker CLI, OCI Artifact와 Local API | Engine별 GGUF·Safetensors | Model Artifact를 Docker Workflow로 관리 |

지원 Architecture와 Quantization은 Release에 따라 바뀐다. “파일 확장자를 읽을 수 있다”와 “해당 Architecture가 정상 동작한다”를 같은 의미로 보지 말고 현재 Compatibility 문서를 확인한다.

### 3.2. Ollama

Registry Model은 `pull` 후 `run`한다.

```bash
ollama pull model-name:tag
ollama run model-name:tag
ollama ps
```

Local GGUF 파일은 `Modelfile`로 등록할 수 있다.

```dockerfile
FROM /srv/models/model-name.Q4_K_M.gguf
PARAMETER temperature 0
PARAMETER num_ctx 4096
```

```bash
ollama create local-model -f Modelfile
ollama run local-model
```

Ollama Native API의 기본 주소는 `http://localhost:11434/api`다.

```bash
curl http://localhost:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-model",
    "stream": false,
    "messages": [
      {"role": "user", "content": "현재 Model 실행 환경을 확인하는 항목을 알려줘."}
    ]
  }'
```

OpenAI-compatible API를 사용하는 Application은 Base URL을 `http://localhost:11434/v1`로 바꿔 연결할 수 있다. 호환 범위는 OpenAI API 전체가 아니므로 Application이 사용하는 Endpoint와 Option을 별도로 시험한다. 실제 Device 배치는 `ollama ps`와 GPU Monitoring 도구를 함께 확인한다.

### 3.3. llama.cpp와 GGUF

`llama.cpp`의 `llama-server`는 GGUF Model을 직접 열고 HTTP Server를 실행한다.

```bash
llama-server \
  --model /srv/models/model-name.Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  --ctx-size 4096 \
  --n-gpu-layers auto
```

`--n-gpu-layers`는 VRAM에 배치할 Layer 수를 제어한다. `auto`가 원하는 결과를 내지 않으면 `llama-server --help`와 시작 Log에서 Backend, Offload된 Layer 수, Context와 Memory 할당을 확인한다. GPU Backend가 포함되지 않은 Binary나 Image를 사용하면 Option을 주어도 CPU로 실행될 수 있다.

```bash
curl http://localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-model",
    "messages": [{"role": "user", "content": "한 문장으로 상태를 응답해줘."}],
    "max_tokens": 64
  }'
```

GGUF의 Quantization Label만으로 필요한 Memory가 정확히 결정되지는 않는다. Weight 외에도 Context에 따른 KV Cache와 Runtime Buffer가 필요하다. GPU에 올리지 못한 Layer는 System RAM과 CPU 연산을 사용하므로 VRAM 절감과 Latency 사이에 Trade-off가 생긴다.

### 3.4. LM Studio

LM Studio는 GUI 외에도 `lms` CLI로 Download, Load와 Server 시작을 제어할 수 있다.

```bash
lms get model-identifier
lms load model-key \
  --identifier local-model \
  --gpu max \
  --context-length 4096
lms server start --port 1234
lms ps
```

Load 전에 Memory 추정만 확인할 수도 있다.

```bash
lms load model-key --context-length 4096 --gpu max --estimate-only
```

```bash
curl http://localhost:1234/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-model",
    "messages": [{"role": "user", "content": "Model Server 연결 시험"}]
  }'
```

기본 Bind 주소인 `127.0.0.1`은 현재 Host에서만 접근된다. `--bind 0.0.0.0` 또는 GUI의 Local Network 제공 기능을 켜면 다른 Host도 접근할 수 있으므로 인증, Firewall과 TLS Proxy를 먼저 구성한다.

### 3.5. Docker Model Runner

Docker Model Runner는 Model을 OCI Artifact처럼 Pull·Cache하고 Engine을 통해 실행한다. 지원 Platform과 GPU Driver 조건은 빠르게 바뀌므로 설치 전에 현재 Requirements를 확인한다.

```bash
docker model version
docker model pull ai/smollm2:360M-Q4_K_M
docker model run ai/smollm2:360M-Q4_K_M "한 문장으로 응답해줘."
docker model ls
```

Host-side TCP가 활성화되어 있다면 기본 Port 예시는 `12434`다.

```bash
curl http://localhost:12434/engines/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "ai/smollm2:360M-Q4_K_M",
    "messages": [{"role": "user", "content": "Docker Model Runner 호출 시험"}]
  }'
```

Container에서 호출할 때와 Host에서 호출할 때 Base URL이 다를 수 있다. Docker Desktop과 Docker Engine도 연결 방식이 다르므로 공식 API Reference에서 현재 경로를 확인한다. Model Runner API 자체에는 인증이 없으므로 신뢰할 수 없는 Network에 직접 노출하지 않는다.

### 3.6. Local 도구 확인 항목

1. 실제 사용 Device와 GPU Offload 비율
2. Model Load 후 RAM·VRAM 사용량
3. 설정된 Context Length와 KV Cache 위치
4. 첫 요청의 Cold Start와 이후 요청 Latency
5. API 인증 유무와 Bind 주소
6. Model을 사용하지 않을 때 Unload되는 조건
7. 동일 요청을 동시에 보냈을 때 Queue와 실패 동작

## 4. vLLM 기반 GPU Model Serving

### 4.1. 적용 범위

vLLM은 생성형 Model을 HTTP API로 제공하고 다수 요청의 Scheduling과 KV Cache를 관리하는 Serving Runtime이다. OpenAI-compatible Endpoint를 제공하므로 기존 Client의 Base URL을 바꿔 연결하기 쉽다.

모든 Architecture, Quantization, GPU와 기능 조합을 동일하게 지원하는 것은 아니다. Model Card뿐 아니라 vLLM의 현재 Supported Models, Quantization 및 Hardware 문서를 확인한다. NLU 전처리·후처리가 강한 Custom API는 5절의 FastAPI 방식이 더 단순할 수 있다.

### 4.2. 단일 GPU Server 실행

```bash
vllm serve /srv/models/instruct-model \
  --served-model-name local-model \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype auto \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.85 \
  --api-key "$VLLM_API_KEY"
```

`--max-model-len`을 Model 최대값으로 그대로 설정하면 KV Cache 공간이 커지고 동시 처리 여유가 줄 수 있다. 실제 입력 정책에 맞는 값으로 시작한다. `--gpu-memory-utilization`도 같은 GPU의 다른 Process, Runtime Workspace와 Memory 변동을 고려해 낮은 값에서 검증한다.

Container Image Tag는 실제로 검증한 Release로 고정한다. 다음 명령의 `VLLM_IMAGE`에는 Digest 또는 Version Tag가 포함된 Image 이름을 주입한다.

```bash
docker run --rm \
  --gpus all \
  --ipc=host \
  -p 127.0.0.1:8000:8000 \
  -v /srv/models:/models:ro \
  "$VLLM_IMAGE" \
  --model /models/instruct-model \
  --served-model-name local-model \
  --max-model-len 4096
```

### 4.3. API 호출

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $VLLM_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-model",
    "messages": [{"role": "user", "content": "GPU Model Server의 상태 확인 항목을 알려줘."}],
    "max_tokens": 128,
    "temperature": 0
  }'
```

```python
import os

from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key=os.environ["VLLM_API_KEY"],
)
response = client.chat.completions.create(
    model="local-model",
    messages=[{"role": "user", "content": "연결 상태를 한 문장으로 응답해줘."}],
    temperature=0,
    max_tokens=64,
)
print(response.choices[0].message.content)
```

OpenAI-compatible이라는 표현은 모든 Option과 응답 동작이 완전히 같다는 뜻이 아니다. Tool Calling, Structured Output, Multimodal Input과 Streaming을 사용하는 경우 각각 Contract Test를 만든다.

### 4.4. Tensor Parallel 실행

Model Weight가 단일 GPU에 들어가지 않거나 여러 GPU의 연산을 함께 사용하려면 Tensor Parallel을 검토한다.

```bash
CUDA_VISIBLE_DEVICES=0,1 \
vllm serve /srv/models/instruct-model \
  --served-model-name local-model \
  --tensor-parallel-size 2 \
  --max-model-len 4096
```

GPU 수를 늘리면 사용 가능한 VRAM 총량은 증가하지만 GPU 사이 Collective Communication이 추가된다. 다음 항목을 함께 확인한다.

- Model Architecture가 지정한 Tensor Parallel 크기를 지원하는가
- GPU 사이가 PCIe인지 NVLink 계열 Interconnect인지
- Process가 의도한 GPU만 볼 수 있는가
- Host RAM이 Weight Loading 중간 단계까지 수용 가능한가
- 단일 GPU 대비 TTFT와 Token/sec가 실제로 개선되는가

```bash
nvidia-smi -L
nvidia-smi topo -m
```

GPU가 여러 장이라는 이유만으로 Tensor Parallel이 항상 빠른 것은 아니다. Model이 단일 GPU에 충분히 들어가고 요청이 독립적이라면 별도 Replica가 더 나을 수 있다.

### 4.5. 시작과 운영 확인

```text
Artifact 읽기
→ Host RAM 사용 증가
→ GPU별 Weight 배치
→ KV Cache·Runtime Buffer 예약
→ API가 Ready 상태로 전환
→ Warm-up 요청
→ 실제 Traffic 허용
```

Model Download와 Load가 끝나기 전에 Traffic을 보내지 않도록 Readiness를 구분한다. 시작 Log에는 Model Revision, dtype, Quantization, Context Length, 사용 GPU와 Parallel 설정을 남긴다.

vLLM의 `--api-key`는 모든 HTTP 경로를 보호하는 Network 보안 장치가 아니다. 공식 문서가 명시한 인증 범위를 확인하고, 외부 제공 시 Reverse Proxy 또는 API Gateway에서 TLS, 인증, 요청 크기 제한과 접근 Log를 적용한다.

## 5. FastAPI 기반 Inference Endpoint

### 5.1. FastAPI를 사용하는 경우

FastAPI는 다음과 같이 Model 전후에 Application Logic이 필요한 Endpoint에 적합하다.

- NLU Text Classification, Named Entity Recognition과 Embedding
- 입력 정규화, 여러 Field 결합과 업무별 Validation
- Label Mapping, Score Threshold와 결과 후처리
- 여러 Model 또는 외부 Model Server를 조합하는 API

대규모 LLM의 Token 생성을 FastAPI Handler 안에서 직접 구현하면 Scheduling과 KV Cache 관리까지 Application 책임이 된다. 이 경우 FastAPI는 인증·업무 Logic을 담당하고 생성은 vLLM 같은 별도 Model Server에 위임하는 구성이 관리하기 쉽다.

### 5.2. NLU Batch Endpoint 예제

다음 `app.py`는 Local Sequence Classification Model을 Process 시작 시 한 번 적재하고 Batch 요청을 처리한다.

```python
import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

import torch
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from transformers import AutoModelForSequenceClassification, AutoTokenizer


MODEL_PATH = os.environ.get("MODEL_PATH", "/models/text-classifier")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "256"))
MAX_BATCH_SIZE = int(os.environ.get("MAX_BATCH_SIZE", "32"))
GPU_CONCURRENCY = int(os.environ.get("GPU_CONCURRENCY", "1"))


@dataclass
class Runtime:
    tokenizer: object | None = None
    model: object | None = None
    device: torch.device | None = None


runtime = Runtime()


class PredictRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class Prediction(BaseModel):
    label: str
    score: float


class PredictResponse(BaseModel):
    model_path: str
    count: int
    predictions: list[Prediction]


@asynccontextmanager
async def lifespan(app: FastAPI):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
    ).to(device)
    model.eval()

    runtime.tokenizer = tokenizer
    runtime.model = model
    runtime.device = device
    app.state.gpu_slots = asyncio.Semaphore(GPU_CONCURRENCY)
    app.state.ready = True

    yield

    app.state.ready = False
    runtime.tokenizer = None
    runtime.model = None
    runtime.device = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan)


def label_name(label_id: int) -> str:
    id2label = runtime.model.config.id2label
    return id2label.get(label_id, id2label.get(str(label_id), str(label_id)))


def infer(texts: list[str]) -> list[Prediction]:
    encoded = runtime.tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    ).to(runtime.device)

    with torch.inference_mode():
        logits = runtime.model(**encoded).logits
        probabilities = torch.softmax(logits, dim=-1)

    scores, label_ids = probabilities.max(dim=-1)
    return [
        Prediction(label=label_name(label_id), score=score)
        for label_id, score in zip(label_ids.tolist(), scores.tolist())
    ]


@app.get("/health")
def health():
    return {"status": "alive"}


@app.get("/ready")
def ready(request: Request):
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="model is not ready",
        )
    return {
        "status": "ready",
        "device": str(runtime.device),
        "model_path": MODEL_PATH,
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest, request: Request):
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(status_code=503, detail="model is not ready")
    if len(payload.texts) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"batch size must be <= {MAX_BATCH_SIZE}",
        )
    if any(not text.strip() for text in payload.texts):
        raise HTTPException(status_code=422, detail="text must not be empty")

    async with request.app.state.gpu_slots:
        predictions = await run_in_threadpool(infer, payload.texts)

    return PredictResponse(
        model_path=MODEL_PATH,
        count=len(predictions),
        predictions=predictions,
    )
```

FastAPI의 `lifespan`은 첫 요청 전에 Model을 적재하고 종료 시 Resource를 정리한다. 요청마다 `from_pretrained()`를 호출하면 Disk I/O와 Weight Loading이 반복된다.

`async` Endpoint로 선언했다고 GPU 연산이 비동기로 바뀌는 것은 아니다. 예제는 Blocking 추론을 Thread Pool로 넘기고 Semaphore로 동시에 GPU에 들어가는 요청 수를 제한한다. 적절한 동시 수는 Model, Batch와 GPU별로 측정해야 한다.

### 5.3. 실행과 호출 시험

```bash
MODEL_PATH=/srv/models/text-classifier \
MAX_BATCH_SIZE=32 \
GPU_CONCURRENCY=1 \
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready

curl http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "texts": [
      "배송이 빨라서 만족합니다.",
      "결제가 계속 실패합니다."
    ]
  }'
```

응답 Label이 `LABEL_0`처럼 나오면 `config.json`의 `id2label`이 업무 Label로 저장되었는지 확인한다. API Code에 Label 순서를 임의로 다시 작성하면 학습 Artifact와 Serving 결과가 어긋날 수 있다.

### 5.4. Worker와 GPU Memory

Uvicorn의 `--workers 2`는 Thread 두 개가 아니라 독립 Process 두 개를 만든다. 각 Process가 `lifespan`을 실행하므로 Model Weight도 각각 RAM·VRAM에 적재된다.

```text
1 Process × Model 1개 → Weight 1개 적재
4 Workers × Model 1개 → 최대 4개 Process가 각각 Weight 적재
```

CPU 위주의 작은 NLU Model은 Multi-worker가 유효할 수 있다. 하나의 GPU에 큰 Model을 올릴 때는 먼저 Worker 하나로 시작한다. 여러 GPU가 있다면 Process별로 GPU를 고정하고 앞단 Load Balancer가 분산하도록 구성할 수 있다.

```bash
CUDA_VISIBLE_DEVICES=0 uvicorn app:app --port 8001 --workers 1
CUDA_VISIBLE_DEVICES=1 uvicorn app:app --port 8002 --workers 1
```

Kubernetes에서는 한 Container 안의 Worker를 늘리기보다 하나의 Process를 가진 Pod를 필요한 수만큼 배치하는 방식을 우선 검토한다. 각 Pod의 GPU 할당과 Model Memory가 명확해지기 때문이다.

### 5.5. Container Image 구성

GPU용 PyTorch Base Image는 [GPU 실행 환경](03_gpu_execution_environment.md)에서 검증한 Tag를 사용한다. 아래 `PYTORCH_IMAGE`와 `APP_VERSION`은 Build 환경에서 주입한다.

```dockerfile
ARG PYTORCH_IMAGE
FROM ${PYTORCH_IMAGE}

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py ./

ENV MODEL_PATH=/models/text-classifier
ENV MAX_LENGTH=256
ENV MAX_BATCH_SIZE=32
ENV GPU_CONCURRENCY=1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

`requirements.txt`에는 Application Package만 두고 Base Image에 포함된 PyTorch와 충돌하는 Version을 다시 설치하지 않도록 확인한다.

```text
fastapi
uvicorn[standard]
transformers
safetensors
```

```bash
docker build \
  --build-arg PYTORCH_IMAGE="$PYTORCH_IMAGE" \
  -t "nlu-api:$APP_VERSION" .

docker run --rm \
  --gpus '"device=0"' \
  -p 127.0.0.1:8000:8000 \
  -v /srv/models/text-classifier:/models/text-classifier:ro \
  "nlu-api:$APP_VERSION"
```

Model을 Volume으로 분리하면 Application Image를 다시 Build하지 않고 Artifact Version을 교체할 수 있다. 대신 Image Version과 Model Revision의 허용 조합을 배포 Manifest에 함께 기록해야 한다.

### 5.6. Endpoint 운영 확인

- `/health`는 Process가 응답 가능한지 확인한다.
- `/ready`는 Model Loading이 끝나 요청을 받을 수 있는지 확인한다.
- Batch 개수뿐 아니라 개별 Text 크기와 전체 Request Body 크기를 제한한다.
- Timeout이 발생해 Client가 연결을 끊었을 때 GPU 작업이 계속 남는지 확인한다.
- Queue 대기 시간과 실제 Model 실행 시간을 분리해 기록한다.
- Model Revision, Device, dtype과 Batch 크기를 Metric 또는 구조화 Log에 남긴다.
- 외부 제공 시 인증, TLS와 Rate Limit을 Application 앞단에 둔다.

## 6. 양자화 Model 실행

### 6.1. 형식과 Runtime 조합

양자화의 원리와 종류는 [AI Models](01_ai_models.md)에서 설명한다. 실행 단계에서는 “몇 Bit인가”보다 Artifact 형식, Quantization Method, Runtime Kernel과 GPU Architecture의 조합이 중요하다.

| 형식·방식 | 주로 사용하는 Runtime | 확인할 항목 |
|---|---|---|
| bitsandbytes 8-bit·4-bit Loading | Transformers | 지원 Device, Compute dtype, CPU Offload 여부 |
| GPTQ·AWQ | Transformers, vLLM 등 | Model별 Config, Runtime과 GPU Kernel 지원 |
| GGUF | llama.cpp, Ollama, LM Studio, Docker Model Runner의 llama.cpp Engine | Architecture, Quantization Variant, GPU Offload |
| FP8 등 Hardware 친화 Precision | vLLM 등 지원 Runtime | GPU 세대, Runtime Build와 Model Config |

지원 목록은 빠르게 변하므로 이 표를 Compatibility 보장 목록으로 사용하지 않는다. Model과 Runtime의 공식 지원 표를 같은 Version 기준으로 확인한다.

### 6.2. Transformers 4-bit Loading 예제

```python
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

model_path = os.environ.get("MODEL_PATH", "/srv/models/instruct-model")
compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=compute_dtype,
)

tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    quantization_config=quantization_config,
    device_map="auto",
    local_files_only=True,
)

print(model.hf_device_map)
print(model.get_memory_footprint())
```

Weight가 4-bit라고 해서 모든 연산과 KV Cache가 4-bit가 되는 것은 아니다. Compute dtype, KV Cache dtype과 양자화되지 않은 Module 때문에 실제 VRAM은 단순한 `Parameter × 0.5 Byte`보다 크다.

### 6.3. Pre-quantized Artifact 확인

GGUF, GPTQ와 AWQ Artifact는 원본 Model과 별개로 다음 정보를 확인한다.

1. 원본 Model과 정확한 Version
2. Quantization 도구와 Method
3. Calibration Dataset 사용 여부
4. Tokenizer와 Chat Template 포함 여부
5. 대상 Runtime과 Hardware에서의 검증 결과
6. 품질 평가와 Benchmark 조건

같은 `Q4` 표기도 Quantization Scheme에 따라 품질과 Kernel이 다르다. 파일 이름만 보고 서로 호환된다고 판단하지 않는다.

### 6.4. CPU·RAM Offload

VRAM이 부족할 때 일부 Weight를 RAM에 두면 Model을 실행할 수 있는 범위가 넓어진다. 그러나 Token 생성 중 CPU와 GPU 사이 Weight 이동 또는 CPU 연산이 발생하면 Latency와 Token/sec가 크게 달라질 수 있다.

```text
VRAM 부족
→ 더 낮은 Precision 검토
→ Context·Batch 축소
→ 일부 CPU Offload
→ 더 작은 Model 또는 더 큰 GPU 검토
```

Offload는 OOM을 피하기 위한 수단이지 성능을 보장하는 방법이 아니다. RAM 용량뿐 아니라 Memory Bandwidth, PCIe Traffic와 CPU 사용률을 함께 측정한다.

### 6.5. 양자화 실행 검증

- 시작 Log에서 실제 Quantization Method와 Kernel을 확인한다.
- Weight, KV Cache와 Runtime Buffer를 포함한 Peak VRAM을 측정한다.
- 동일 Prompt·Seed 조건으로 품질을 비교한다.
- 짧은 Prompt와 긴 Prompt에서 TTFT를 각각 측정한다.
- 단일 요청과 동시 요청에서 Token/sec와 Throughput을 구분한다.
- 지원되지 않는 Kernel이 다른 구현으로 Fallback되는지 확인한다.

## 7. 실행 방식 비교

### 7.1. 선택 기준

| 요구사항 | 먼저 검토할 방식 | 이유 |
|---|---|---|
| NLU·분류 Model의 Custom Schema와 후처리 | Transformers + FastAPI | 전처리, Label과 Response를 직접 제어하기 쉽다. |
| Offline Batch 또는 Model Code 검증 | Transformers 직접 실행 | Server 없이 실행 흐름을 확인할 수 있다. |
| 개인 PC에서 빠른 LLM 시험 | Ollama 또는 LM Studio | Download, Load와 호출 과정이 단순하다. |
| GGUF의 세부 CPU·GPU Offload 제어 | llama.cpp | 실행 Option과 Backend를 직접 선택할 수 있다. |
| Docker Workflow로 Local Model 관리 | Docker Model Runner | Model을 OCI Artifact와 Docker CLI로 다룰 수 있다. |
| GPU Server에서 생성형 Model의 동시 Serving | vLLM | Request Scheduling과 KV Cache 관리 기능을 제공한다. |

표는 출발점을 제시할 뿐이다. 최종 선택은 Model 지원, Hardware, 요청 형태와 Benchmark 결과로 결정한다.

### 7.2. 실행 전 확인 절차

```text
1. Task와 API Schema 결정
2. Model Revision·License·Artifact 형식 확인
3. Weight와 Context 기준 RAM·VRAM 산정
4. Hardware를 지원하는 Runtime 후보 선정
5. Local 단일 요청으로 결과 검증
6. API Server에서 Warm-up과 동시 요청 시험
7. OOM, Timeout, 재시작과 Model Reload 시험
8. 인증·TLS·Network 노출 범위 확인
9. Version과 Benchmark 조건 기록
```

VRAM 산정은 [Infrastructure Sizing](05_infrastructure_sizing.md), GPU Compute와 Memory 병목은 [GPU System](02_gpu_system.md)의 기준을 사용한다.

### 7.3. 공통 실패 형태

| 증상 | 먼저 확인할 항목 |
|---|---|
| Model을 찾지 못함 | Mount 경로, Cache 경로, File 권한과 Revision |
| Tokenizer 오류 | Tokenizer File 누락, Model과 다른 Revision, Chat Template |
| CUDA OOM | Weight dtype, Context, Batch, KV Cache, Worker·Replica 수 |
| GPU가 사용되지 않음 | PyTorch CUDA 인식, Runtime의 GPU Backend, Device Mapping |
| 시작 시간이 지나치게 김 | Network Download, Disk Throughput, Shard 수, Host RAM |
| 첫 요청만 느림 | On-demand Model Load, Kernel 초기화와 Warm-up |
| 출력 품질이 이상함 | Base·Instruct 구분, Prompt Template, Quantization, Tokenizer |
| 동시 요청에서 급격히 느려짐 | Queue, Batch Policy, Context 분포, CPU Tokenization |
| Process 수 증가 후 OOM | Worker·Replica별 Model 중복 적재 |
| API가 외부에서 열림 | Bind 주소, Firewall, 인증과 Reverse Proxy 설정 |

## 8. References

확인일: 2026-09-15

- [Hugging Face Hub — Download files from the Hub](https://huggingface.co/docs/huggingface_hub/guides/download)
- [Hugging Face Hub — Cache management](https://huggingface.co/docs/huggingface_hub/guides/manage-cache)
- [Hugging Face Transformers — Models](https://huggingface.co/docs/transformers/main_classes/model)
- [Hugging Face Transformers — Quantization](https://huggingface.co/docs/transformers/main/quantization/overview)
- [Hugging Face Transformers — bitsandbytes](https://huggingface.co/docs/transformers/main/quantization/bitsandbytes)
- [Hugging Face Transformers — Custom models](https://huggingface.co/docs/transformers/custom_models)
- [Hugging Face — Inference Providers](https://huggingface.co/docs/inference-providers/index)
- [vLLM — OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/)
- [vLLM — `vllm serve` CLI](https://docs.vllm.ai/en/latest/cli/serve/)
- [Ollama — API Introduction](https://docs.ollama.com/api/introduction)
- [Ollama — Importing a Model](https://docs.ollama.com/import)
- [Ollama — OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [llama.cpp — `llama-server`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [LM Studio — CLI](https://lmstudio.ai/docs/cli)
- [LM Studio — REST API](https://lmstudio.ai/docs/developer/rest)
- [Docker — Docker Model Runner](https://docs.docker.com/ai/model-runner/)
- [Docker — Model Runner API Reference](https://docs.docker.com/ai/model-runner/api-reference/)
- [FastAPI — Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI — Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/)
- [FastAPI — FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/)
