from elasticsearch import AsyncElasticsearch

def get_es_client(config):
    """
    Elasticsearch 비동기 클라이언트 생성
    :param config: ConfigParser 객체
    """
    # config.ini의 [elasticsearch] 섹션 읽기
    es_conf = config['elasticsearch']
    
    # URL 조립 (http://127.0.0.1:9200)
    scheme = es_conf.get('scheme', 'http')
    host = es_conf.get('host', 'localhost')
    port = es_conf.get('port', '9200')
    full_url = f"{scheme}://{host}:{port}"
    
    # 인증 정보 확인
    user = es_conf.get('user')
    password = es_conf.get('password')
    
    auth = (user, password) if user and password else None

    # 클라이언트 반환
    return AsyncElasticsearch(
        [full_url], 
        basic_auth=auth, 
        request_timeout=60
    )
