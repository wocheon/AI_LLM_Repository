docker rm kobert_request_batch -f

docker run -d --network=app-network --name kobert_request_batch \
        -v "$(pwd)":/app  \
        kobert_request_batch:latest

docker logs kobert_request_batch -f

