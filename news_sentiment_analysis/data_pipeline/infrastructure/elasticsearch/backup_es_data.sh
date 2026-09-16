
# snapshot repo 생성 
curl -X PUT "localhost:9200/_snapshot/my_backup_repo?pretty" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/usr/share/elasticsearch/backup"
  }
}
'

# 스냅샷 이름: snapshot_20260127
curl -X PUT "localhost:9200/_snapshot/my_backup_repo/snapshot_20260128?wait_for_completion=true&pretty"


# 스냅샷 생성 확인 
curl -X GET "localhost:9200/_snapshot/my_backup_repo/snapshot_20260128?pretty"



# 참고 - 스냅샷 복구 방법 

# 1. 인덱스 닫기 (잠시 중지)
#curl -X POST "localhost:9200/dataset_articles/_close?pretty"

# 2. 복구 실행
#curl -X POST "localhost:9200/_snapshot/my_backup_repo/snapshot_20260127/_restore?wait_for_completion=true&pretty"

# 3. 인덱스 다시 열기
#curl -X POST "localhost:9200/dataset_articles/_open?pretty"
