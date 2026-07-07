docker rm llm_qwen3_4b_request_batch -f

docker run -d --rm --network=app-network --name llm_qwen3_4b_request_batch -v "$(pwd)":/app llm_qwen3_4b_request_batch:latest

docker logs llm_qwen3_4b_request_batch -f

