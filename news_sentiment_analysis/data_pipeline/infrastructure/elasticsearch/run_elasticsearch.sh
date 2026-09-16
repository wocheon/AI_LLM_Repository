docker run -d --name elasticsearch \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "xpack.security.http.ssl.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  --network=app-network \
  -v ./esdata:/usr/share/elasticsearch/data  \
  -p 9200:9200 \
  docker.elastic.co/elasticsearch/elasticsearch:9.0.4
#  --memory=1g --memory-swap=1g \    # 리소스 제한 필요시 활성화 
