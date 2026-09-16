import os
from elasticsearch import Elasticsearch
from utils.config_loader import config_loader

_es_client = None

def get_es_client():
    """
    Elasticsearch 클라이언트를 반환하는 싱글톤 함수.
    최초 호출 시 연결을 생성하고 이후에는 재사용합니다.
    """
    es_conf = config_loader.get_section('elasticsearch')
    global _es_client
    if _es_client is None:
        host = es_conf.get('host', 'elasticsearch')
        port = int(es_conf.get('port', 9200))
        url = f"http://{host}:{port}"
        
        # 연결 타임아웃 등 설정
        _es_client = Elasticsearch(
            url,
            request_timeout=60,
            max_retries=3,
            retry_on_timeout=True
        )
    return _es_client
