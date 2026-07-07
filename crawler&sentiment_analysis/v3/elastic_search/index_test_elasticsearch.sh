#!/bin/bash

echo "### 신규 문서 추가"
curl -X POST "http://localhost:9200/test-index/_doc/test_doc" -H 'Content-Type: application/json' -d'
{
  "user": "testuser",
  "message": "Hello Elasticsearch",
  "description" : "Test Elastic Search Document"
}'

echo ""
echo ""
echo "### 문서 조회"
curl -X GET "http://localhost:9200/test-index/_doc/test_doc"


echo ""
echo ""
echo "### 문서 삭제"
curl -X DELETE "http://localhost:9200/test-index/_doc/test_doc"
echo ""