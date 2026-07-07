echo "#1. 컨테이너 동작 확인"
curl -X GET "http://localhost:9200/"

echo "#2. 클러스터 상태 확인"
curl -X GET "http://localhost:9200/_cluster/health?pretty"