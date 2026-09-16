#!/bin/bash
docker rm sentiment_model_fastapi -f

docker run -d --rm -p 8000:8000 --network app-network --name sentiment_model_fastapi \
        -v ../models/kobert/kobert_fintuned/:/models/kobert \
	-v ../models/koelectra/KoELECTRA_fine_tunning_emotion/:/models/koelectra \
        -v "$(pwd)":/app  \
        sentiment_model_fastapi:latest

docker logs sentiment_model_fastapi -f
