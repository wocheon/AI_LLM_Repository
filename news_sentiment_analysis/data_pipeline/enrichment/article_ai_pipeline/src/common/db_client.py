import pymysql

def get_db_conn(config):
    """
    PyMySQL 동기 커넥션 생성
    :param config: ConfigParser 객체
    """
    # config.ini의 [database] 섹션 읽기
    db_conf = config['database']
    
    return pymysql.connect(
        host=db_conf['host'],
        port=int(db_conf.get('port', 3306)),
        user=db_conf['user'],
        password=db_conf['password'],
        db=db_conf['db_name'],  # config.ini 키 이름 확인 (db_name)
        charset=db_conf.get('charset', 'utf8mb4'),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
