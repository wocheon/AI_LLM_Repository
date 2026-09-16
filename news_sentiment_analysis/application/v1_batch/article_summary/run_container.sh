docker rm -f es_article_summarizer 


docker run --rm -d \
  --name es_article_summarizer \
  --network app-network \
  -v $(pwd)/config.ini:/app/config/config.ini \
  es-summarizer:latest

docker logs -f es_article_summarizer

