curl -X POST "localhost:9200/_reindex?pretty" -H 'Content-Type: application/json' -d'
{
  "source": {
    "remote": {
      "host": "http://외부서버IP:9200",
      "username": "elastic_user",
      "password": "elastic_password"
    },
    "index": "dataset_articles",
    "query": {
      "range": {
        "crawled_at": {
          "gte": "2026-01-28"
        }
      }
    }
  },
  "dest": {
    "index": "dataset_articles"
  }
}
'
