
# **Ollama vs vLLM: 동시 요청 처리 성능 비교**

## 개요 
- Ollama와 vLLM은 로컬 LLM 추론을 위한 강력한 도구이지만, 동시 요청 처리(Concurrent Request Handling) 방식과 성능에서 큰 차이 존재
- 두 도구 간의 핵심 설계 철학 및 KV Cache 관리 방식의 차이를 확인

## **1. KV Cache (Key-Value Cache)란?**

- **KV Cache**
    - Transformer 기반 LLM은 각 토큰을 생성할 때마다 이전 토큰들의 Key(K)와 Value(V) 벡터를 계산하고 저장
    - 이 K와 V 벡터들은 다음 토큰 생성 시 어텐션(Attention) 계산에 재사용되어 연산량 감소에 도움을 줌

*   **KV Cache의 중요성**:
    *   **속도 향상**: 매번 K, V 벡터를 재계산하는 대신 캐시된 값을 사용하므로 추론 속도가 증가
    *   **메모리 사용**: KV Cache는 GPU 메모리(VRAM)를 많이 차지하며, 컨텍스트 길이(프롬프트 + 생성된 토큰)가 길어질수록 필요한 메모리 양이 선형적으로 증가

## **2. Ollama의 동시 요청 처리 및 KV Cache 관리**

- Ollama는 `llama.cpp`를 기반으로 하며, 기본적으로 **단일 모델 인스턴스**를 통해 요청을 처리

*   **KV Cache 관리 방식**:
    *   Ollama는 요청이 들어올 때마다 해당 요청에 필요한 KV Cache를 할당하고, 요청 처리가 완료되면 해당 캐시를 해제하거나 일정 시간(`keep_alive`) 동안 유지
    *   여러 동시 요청이 들어오면, Ollama는 이 요청들을 **순차적으로 처리**하거나, 내부적으로 제한된 수의 스레드를 사용하여 **제한적인 병렬 처리**를 시도
    *   각 요청은 독립적인 KV Cache를 사용하며, 이 캐시들은 서로 공유되지 않음

*   **동시 요청 처리의 한계**:
    *   **순차 처리 병목**: 여러 요청이 동시에 들어와도 실제로는 하나씩 처리되는 경향이 강하여, 첫 번째 요청이 완료될 때까지 다음 요청은 대기


## **3. vLLM의 동시 요청 처리 및 PagedAttention**

vLLM은 고성능 추론 및 서빙을 위해 설계되었으며, 특히 **PagedAttention**이라는 혁신적인 메모리 관리 기법을 통해 동시 요청 처리 효율을 극대화

*   **PagedAttention (KV Cache 관리 방식)**:
    *   **운영체제의 가상 메모리 개념 도입**: vLLM은 KV Cache를 연속된 메모리 공간에 할당하는 대신, 고정된 크기의 **블록(Block)** 단위로 분할. 
        - 마치 운영체제가 가상 메모리를 물리 메모리의 페이지(Page)에 매핑하는 것과 유사

    *   **비연속 메모리 할당**: 논리적으로는 연속된 토큰들이라도 물리적으로는 비연속적인 블록에 저장 가능
        - 메모리 단편화(Fragmentation)를 사실상 제거

    *   **동적 할당**: 필요할 때마다 블록 단위로 메모리를 할당하므로, 미리 큰 메모리 공간을 예약해 둘 필요가 없어 메모리 낭비를 최소화

*   **Continuous Batching (지속적 배칭)**:
    *   **요청 즉시 병합**: vLLM은 요청이 들어오는 즉시 실행 중인 배치(Batch)에 합류
        -  먼저 끝난 요청의 자리를 새로운 요청이 즉시 채우는 방식

    *   **GPU 활용률 극대화**: GPU가 쉬는 시간(Idle time) 없이 항상 연산을 수행하도록 하여 처리량(Throughput)을 비약적으로 향상

## **4. 성능 비교: Ollama vs vLLM**

| 비교 항목 | **Ollama (llama.cpp 기반)** | **vLLM (PagedAttention 기반)** |
| :--- | :--- | :--- |
| **처리 방식** | **순차적 처리 (Sequential)** 위주<br>(제한적 병렬 처리 지원) | **Continuous Batching**<br>(요청 즉시 동적 배칭) |
| **KV Cache 효율** | **낮음** (메모리 단편화 및 패딩 낭비 심함) | **매우 높음** (단편화 0%에 가까움, 메모리 공유) |
| **동시성 (Concurrency)** | **낮음** (동시 요청 시 대기 시간 급증) | **매우 높음** (수백 개의 동시 요청도 효율적 처리) |
| **Throughput (TPS)** | 상대적으로 낮음 (GPU 유휴 시간 발생) | **압도적으로 높음** (Ollama 대비 최대 10~20배)  |
| **주요 용도** | 개인 로컬 사용, 단일 사용자 채팅 | **대규모 배포, 서버용 API, 고성능 배치 처리** |

## **5. 결론: 언제 무엇을 써야 할까?**

*   **Ollama를 선택해야 할 때**:
    *   개인 PC(MacBook 등)나 단일 GPU 환경에서 간편하게 LLM을 실행하고 싶을 때.
    *   복잡한 설정 없이 `ollama run` 명령어 한 번으로 대화형 인터페이스(CLI)를 사용하고 싶을 때.
    *   동시 요청이 거의 없고, 한 번에 하나의 질문만 처리하는 경우.

*   **vLLM을 선택해야 할 때**:
    *   **시간당 2회 x 다수의 배치 작업**처럼 동시에 여러 요청을 처리해야 하는 엔터프라이즈 환경.
    *   T4, A100 등 서버급 GPU 자원의 효율을 극대화하여 비용을 절감해야 할 때.
    *   API 서버로 구축하여 다수의 클라이언트 요청을 안정적으로 처리해야 할 때.


## 6. 동시 요청 처리 테스트 
- 대상 모델 : qwen3:0.6B 
- 각각 ollama, vllm docker 컨테이너를 실행 하여 동시 요청 처리에 대한 차이를 확인

### docker container 실행 - ollama

```bash
# ollama docker container 실행
docker run -d --restart=always --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# qwen3:0.6b 모델 다운로드 및 실행
docker exec -it ollama ollama run qwen3:0.6b
```


### docker container 실행 - vLLM

```bash
#### vLLM 용 Qwen3:0.6B모델(테스트용) ####
# --model Qwen/Qwen3-0.6B \

# vLLM 실행 옵션
#--max-model-len : 최대 context 길이(토큰 수)
#--max-num-seqs : 한 iteration에서 동시에 처리할 시퀀스 개수 (기본값 256)
#--gpu-memory-utilization : GPU 메모리 사용 비율 (0~1, 기본값 0.9).
#--tensor-parallel-size 2 : GPU 2대면 병렬 설정 필요
# --enforce-eager : CUDA Graph 비활성화를 통해 VRAM 사용률 감소  및 단일 요청 처리 속도 증가

# Deploy with docker on Linux:
docker run -d --runtime nvidia --gpus all \
        --name vllm_container \
        -v ~/.cache/huggingface:/root/.cache/huggingface \
        --env "HUGGING_FACE_HUB_TOKEN=xxxxxxxxxxx" \
        -p 8000:8000 \
        --ipc=host \
        vllm/vllm-openai:latest \
        --model Qwen/Qwen3-0.6B  \
        --max-model-len 4096 \
        --max-num-seqs 128 \
        --gpu-memory-utilization 0.7
```

### 동시 API 요청 테스트용 스크립트 구성 
```bash
#!/usr/bin/env bash

CONCURRENCY=5
TOOL="ollama"

if [ $TOOL == 'ollama' ]; then
    ########### ollama API ################
    ENDPOINT="http://localhost:11434/v1/chat/completions"
    MODEL="qwen3:0.6b"
    #####################################
else
    ########### vLLM API #################
    ENDPOINT="http://localhost:8000/v1/chat/completions"
    MODEL="Qwen/Qwen3-0.6B"
    #####################################
fi    


one_call() {
  local i="$1"
  local start_ns=$(date +%s%N)

  local resp=$(curl -s "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${MODEL}\",
      \"messages\": [
        {\"role\": \"user\", \"content\": \"Request ${i}: vLLM 병렬 처리 테스트.\"}
      ],
      \"max_tokens\": 32,
      \"temperature\": 0.0
    }")

  local end_ns=$(date +%s%N)
  local elapsed_ns=$((end_ns - start_ns))
  local elapsed_sec=$(printf "%.3f" "$(echo "$elapsed_ns / 1000000000" | bc -l)")

  # 응답 내용 추출 (처음 50자만)
  #local answer=$(echo "$resp" | jq -r '.choices[0].message.content' | head -c 150)
  local answer=$(echo "$resp")

  echo "┌─ [${i}] ${elapsed_sec}s"
  echo "│  Answer: ${answer}..."
  echo "└─────────"
}

export -f one_call
export ENDPOINT MODEL

echo "=== $TOOL - API 요청 처리 테스트 (동시 ${CONCURRENCY}개 요청) ==="
echo "GPU 사용률 확인: 다른 터미널에서 'watch -n1 nvidia-smi' 실행하세요"
echo

time seq 1 "$CONCURRENCY" | xargs -I{} -P"$CONCURRENCY" bash -c 'one_call "$@"' _ {}

echo
echo "=== 테스트 완료 ==="
echo "GPU 사용률이 80%+로 올라가고, 응답 시간이 비슷하게 나오면 병렬 처리 정상!"
```



### ollama 동시요청 테스트 결과 
- ollama의 경우, 하나의 요청이 끝나면 다음요청이 처리되는 식으로 진행됨
    - 한번에 여러 요청을 동시 처리 불가 

```bash
$ bash test_api_parallel.sh
=== ollama - API 요청 병렬 처리 테스트 (동시 16개 요청) ===
GPU 사용률 확인: 다른 터미널에서 'watch -n1 nvidia-smi' 실행하세요

┌─ [1] 0.692s
│  Answer: {"id":"chatcmpl-485","object":"chat.completion","created":1766393607,"model":"qwen3:0.6b","system_fingerprint":"fp_ollama","choices":[{"index":0,"message":{"role":"assistant","content":"","reasoning":"Okay, the user is asking about testing VLLM for parallel processing. Let me break this down. First, I need to explain what V"},"finish_reason":"length"}],"usage":{"prompt_tokens":25,"completion_tokens":32,"total_tokens":57}}...
└─────────
┌─ [3] 0.863s
│  Answer: {"id":"chatcmpl-670","object":"chat.completion","created":1766393607,"model":"qwen3:0.6b","system_fingerprint":"fp_ollama","choices":[{"index":0,"message":{"role":"assistant","content":"LL\u003cthink\u003e\nOkay, the user is asking about testing parallel processing in vLLM. Let me start by recalling what vLLM is. It's a"},"finish_reason":"length"}],"usage":{"prompt_tokens":25,"completion_tokens":32,"total_tokens":57}}...
└─────────
┌─ [2] 1.050s
│  Answer: {"id":"chatcmpl-557","object":"chat.completion","created":1766393608,"model":"qwen3:0.6b","system_fingerprint":"fp_ollama","choices":[{"index":0,"message":{"role":"assistant","content":" large\u003cthink\u003e\nOkay, the user is asking about testing parallel processing in vLLM. Let me start by recalling what vLLM is. It's a"},"finish_reason":"length"}],"usage":{"prompt_tokens":25,"completion_tokens":32,"total_tokens":57}}...
└─────────
.....

┌─ [15] 3.494s
│  Answer: {"id":"chatcmpl-220","object":"chat.completion","created":1766393610,"model":"qwen3:0.6b","system_fingerprint":"fp_ollama","choices":[{"index":0,"message":{"role":"assistant","content":" library\u003cthink\u003e\nOkay, the user is asking about testing VLLM parallel processing. Let me break this down. First, I need to explain what VLL"},"finish_reason":"length"}],"usage":{"prompt_tokens":26,"completion_tokens":32,"total_tokens":58}}...
└─────────

real    0m3.520s
user    0m0.318s
sys     0m0.099s

=== 테스트 완료 ===
GPU 사용률이 80%+로 올라가고, 응답 시간이 비슷하게 나오면 병렬 처리 정상!

```

### vLLM 동시요청 테스트 결과 
- vLLM 의 경우, 여러 요청이 동시에 실행되어 비슷한 시간에 종료됨을 확인    
    - 한번에 여러 요청을 동시 처리 가능 
- 초소형 모델에서는 vLLM의 파이썬 스케줄링 오버헤드가 더 크므로, 응답 속도가 느려질수 있음
    - 모델 크기가 4B이상으로 올라가면 vLLM이 더 유리            

```bash
$ bash test_api_parallel.sh
===  vLLM - API 요청 병렬 처리 테스트 (동시 16개 요청) ===
GPU 사용률 확인: 다른 터미널에서 'watch -n1 nvidia-smi' 실행하세요

┌─ [1] 4.077s
│  Answer: {"id":"chatcmpl-ac989a826dcfa4cf","object":"chat.completion","created":1766393737,"model":"Qwen/Qwen3-0.6B","choices":[{"index":0,"message":{"role":"assistant","content":"<think>\nOkay, the user is asking about a vLLM parallel processing test. Let me start by recalling what vLLM is. It's a library","refusal":null,"annotations":null,"audio":null,"function_call":null,"tool_calls":[],"reasoning":null,"reasoning_content":null},"logprobs":null,"finish_reason":"length","stop_reason":null,"token_ids":null}],"service_tier":null,"system_fingerprint":null,"usage":{"prompt_tokens":23,"total_tokens":55,"completion_tokens":32,"prompt_tokens_details":null},"prompt_logprobs":null,"prompt_token_ids":null,"kv_transfer_params":null}...
└─────────
┌─ [3] 4.076s
│  Answer: {"id":"chatcmpl-9c157a95e8c903d0","object":"chat.completion","created":1766393737,"model":"Qwen/Qwen3-0.6B","choices":[{"index":0,"message":{"role":"assistant","content":"<think>\nOkay, the user is asking about testing vLLM for parallel processing. Let me start by recalling what vLLM does. It's a library","refusal":null,"annotations":null,"audio":null,"function_call":null,"tool_calls":[],"reasoning":null,"reasoning_content":null},"logprobs":null,"finish_reason":"length","stop_reason":null,"token_ids":null}],"service_tier":null,"system_fingerprint":null,"usage":{"prompt_tokens":23,"total_tokens":55,"completion_tokens":32,"prompt_tokens_details":null},"prompt_logprobs":null,"prompt_token_ids":null,"kv_transfer_params":null}...
└─────────
┌─ [9] 4.101s
│  Answer: {"id":"chatcmpl-8c4331b40a63d144","object":"chat.completion","created":1766393737,"model":"Qwen/Qwen3-0.6B","choices":[{"index":0,"message":{"role":"assistant","content":"<think>\nOkay, the user is asking about testing vLLM for parallel processing. Let me start by recalling what vLLM does. It's a library","refusal":null,"annotations":null,"audio":null,"function_call":null,"tool_calls":[],"reasoning":null,"reasoning_content":null},"logprobs":null,"finish_reason":"length","stop_reason":null,"token_ids":null}],"service_tier":null,"system_fingerprint":null,"usage":{"prompt_tokens":23,"total_tokens":55,"completion_tokens":32,"prompt_tokens_details":null},"prompt_logprobs":null,"prompt_token_ids":null,"kv_transfer_params":null}...
└─────────

....

┌─ [15] 4.089s
│  Answer: {"id":"chatcmpl-a2045d97d5796353","object":"chat.completion","created":1766393737,"model":"Qwen/Qwen3-0.6B","choices":[{"index":0,"message":{"role":"assistant","content":"<think>\nOkay, the user is asking about testing vLLM for parallel processing. Let me start by recalling what vLLM is. It's a library","refusal":null,"annotations":null,"audio":null,"function_call":null,"tool_calls":[],"reasoning":null,"reasoning_content":null},"logprobs":null,"finish_reason":"length","stop_reason":null,"token_ids":null}],"service_tier":null,"system_fingerprint":null,"usage":{"prompt_tokens":24,"total_tokens":56,"completion_tokens":32,"prompt_tokens_details":null},"prompt_logprobs":null,"prompt_token_ids":null,"kv_transfer_params":null}...
└─────────

real    0m4.120s
user    0m0.256s
sys     0m0.163s

=== 테스트 완료 ===
GPU 사용률이 80%+로 올라가고, 응답 시간이 비슷하게 나오면 병렬 처리 정상!
```


### 참고 - qwen:4B 모델에서 테스트 결과
- vllm 
    - 모델 : qwen3:4b-AWQ
    - 결과 
        -  real    0m3.950s

- ollama 
    - 모델 : qwen3:4b-Q4_K_M
    - 결과 
        - real    0m3.950s

-> **모델이 커질수록 vLLM 쪽이 더 빠른 응답속도를 보임**