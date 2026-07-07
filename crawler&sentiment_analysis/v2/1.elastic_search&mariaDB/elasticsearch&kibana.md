# Elastic Search & Kibana 실행 
- 기사 본문 내용을 저장하기 위한 ElasticSearch 실행 
- kibana를 통해 ElasticSearch의 Web UI 사용


## ElasticSearch 및 Kibana 실행 
- Docker를 통해 실행 
- 필요시 리소스 제한 사용

### Elasticsearch 컨테이너 실행
- HTTPS off 
- 보안기능 비활성화
- single-node로 실행

```bash
docker run -d --name elasticsearch \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "xpack.security.http.ssl.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  -v ./esdata:/usr/share/elasticsearch/data  \
  --memory=1g --memory-swap=1g \    # 리소스 제한 필요시 활성화 
  -p 9200:9200 \
  docker.elastic.co/elasticsearch/elasticsearch:9.0.4
```

### ElasticSearch용 웹UI Kibana 실행 
- ElasticSearch 주소를 Environment로 사용 

```bash
docker run -d --name kibana --network=host \
  -e "ELASTICSEARCH_HOSTS=http://localhost:9200" \
  docker.elastic.co/kibana/kibana:9.0.4
```

### ElasticSearch 정상동작 확인 
```
echo "#1. 컨테이너 동작 확인"
curl -X GET "http://localhost:9200/"

echo "#2. 클러스터 상태 확인"
curl -X GET "http://localhost:9200/_cluster/health?pretty"
```

### Kibana 정상 동작 확인 
- 실행 후 5601 포트를 통해 웹브라우저로 접근 
    - http://localhost:5601


## ElasticSearch 사용 방법

### 신규 문서 추가
- Index `test-index`를 만들고 해당 Index에 새로운 문서 `test_doc` 추가

```bash
# 문서 추가 (Index에 문서 삽입)
curl -X POST "http://localhost:9200/test-index/_doc/test_doc" -H 'Content-Type: application/json' -d'
{
  "user": "testuser",
  "message": "Hello Elasticsearch",
  "description" : "Test Elastic Search Document"
}'

# 결과
{"_index":"test-index","_id":"test_doc","_version":1,"result":"created","_shards":{"total":2,"successful":1,"failed":0},"_seq_no":1,"_primary_term":1}
```
### 문서 조회
- 생성된 `test-index` 내 `test_doc` 문서 조회

```bash
# 문서 조회
curl -X GET "http://localhost:9200/test-index/_doc/test_doc"

{"_index":"test-index","_id":"test_doc","_version":1,"_seq_no":1,"_primary_term":1,"found":true,"_source":
{
  "user": "testuser",
  "message": "Hello Elasticsearch",
  "description" : "Test Elastic Search Document"
}}r
```

### 문서 삭제
- 생성된 `test-index` 내 `test_doc` 문서 삭제제
```bash
# 문서 삭제
curl -X DELETE "http://localhost:9200/test-index/_doc/test_doc"
```

### Index 삭제 

- 생성된 `test-index` 삭제 
```bash
# Index 삭제
curl -X DELETE "http://localhost:9200/test-index"
```