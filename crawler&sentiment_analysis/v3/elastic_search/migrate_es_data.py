from elasticsearch import Elasticsearch, helpers
import sys

# --- 설정 ---
# 타임아웃을 5분(300초)으로 넉넉하게 설정
TIMEOUT_SEC = 300 

# ES #1 (Local Source)
es_source = Elasticsearch(
    "http://localhost:9200", 
    basic_auth=("user", "pass"),
    request_timeout=TIMEOUT_SEC  # Global Request Timeout 설정
)

# ES #2 (Remote Target)
es_target = Elasticsearch(
    "http://34.22.104.188:9200", 
    basic_auth=("admin", "pass"),
    request_timeout=TIMEOUT_SEC  # Global Request Timeout 설정
)

INDEX_NAME = "dataset_articles"
BACKUP_NAME = "dataset_articles_backup"


def migrate():
    # 1. Target 연결 확인
    try:
        if not es_target.ping():
            print("Error: Target 서버에 연결할 수 없습니다.")
            sys.exit(1)
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)

    # 2. [Target] 백업 및 기존 인덱스 삭제
    if es_target.indices.exists(index=INDEX_NAME):
        print(f">>> [Target] 기존 '{INDEX_NAME}'를 '{BACKUP_NAME}'으로 백업 중...")
        try:
            es_target.reindex(
                body={
                    "source": {"index": INDEX_NAME},
                    "dest": {"index": BACKUP_NAME}
                },
                wait_for_completion=True,
                request_timeout=TIMEOUT_SEC
            )
            print(f">>> [Target] 기존 인덱스 삭제: {INDEX_NAME}")
            es_target.indices.delete(index=INDEX_NAME, request_timeout=TIMEOUT_SEC)
        except Exception as e:
            print(f"Backup failed: {e}")
            sys.exit(1)


    print(f">>> [Migration] 데이터 전송 시작...")
    
    try:
        # [Fix] request_timeout 인자 위치 수정
        success, failed = helpers.reindex(
            client=es_source,
            source_index=INDEX_NAME,
            target_index=INDEX_NAME,
            target_client=es_target,
            chunk_size=1000,
            scroll='10m',
            # request_timeout을 직접 넣지 않고, kwargs로 전달될 수 있도록 수정하거나
            # bulk 요청에 대한 설정은 아래와 같이 전달합니다.
            target_kwargs={"request_timeout": TIMEOUT_SEC} 
        )
        print(f"\n>>> [Complete] 성공: {success}건, 실패: {failed}건")
        
    except TypeError as e:
        # 만약 target_kwargs도 지원하지 않는 구버전 클라이언트라면
        # 단순히 request_timeout을 제거하고 client의 전역 설정을 따르게 합니다.
        print(f"[Warn] 인자 오류 발생 ({e}). 기본 설정으로 재시도합니다.")
        success, failed = helpers.reindex(
            client=es_source,
            source_index=INDEX_NAME,
            target_index=INDEX_NAME,
            target_client=es_target,
            chunk_size=1000,
            scroll='10m'
        )
        print(f"\n>>> [Complete] 성공: {success}건, 실패: {failed}건")
        
    except Exception as e:
        print(f"\n>>> [Error] Migration 중 오류 발생: {e}")

if __name__ == "__main__":
    migrate()
