docker run -d -p 5601:5601 --name kibana --network="app-network" \
  -e "ELASTICSEARCH_HOSTS=http://elasticsearch:9200" \
  docker.elastic.co/kibana/kibana:9.0.4

#-e "ELASTICSEARCH_HOSTS=http://localhost:9200" \  
