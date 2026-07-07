#!/bin/bash

model='ai/qwen3'
prompt_msg='Ubuntu 20.04 LTS의 EOL(End of Life) 날짜는 언제인가요?'

# host.docker.internal 또는 localhost 사용 (환경에 맞게 선택)
TARGET_URL="http://localhost:12434/engines/llama.cpp/v1/chat/completions"

curl -s "$TARGET_URL" \
  -H "Content-Type: application/json" \
  -d "{
        \"model\": \"$model\",
        \"messages\": [
                {\"role\": \"system\", \"content\": \"You are a helpful assistant.\"},
                {\"role\": \"user\", \"content\": \"$prompt_msg\"}
        ]
      }" | jq .

