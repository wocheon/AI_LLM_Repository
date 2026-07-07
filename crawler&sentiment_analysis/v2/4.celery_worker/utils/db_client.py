import os
import logging
import mysql.connector
from utils.config_loader import config_loader

logger = logging.getLogger(__name__)

def get_db_conn():
    """
    config.ini -> 환경변수 -> 기본값 순서로 DB 연결 정보를 로드
    """
    try:
        # 1. Config Loader에서 'mysql' 섹션 가져오기
        db_conf = config_loader.get_section('mysql')
        
        # 2. 값 추출 (없으면 환경변수 확인)
        host = db_conf.get('host') or os.getenv('DB_HOST', 'mysql')
        port = int(db_conf.get('port') or os.getenv('DB_PORT', 3306))
        user = db_conf.get('user') or os.getenv('DB_USER', 'root')
        password = db_conf.get('password') or os.getenv('DB_PASSWORD', 'root')
        database = db_conf.get('database') or os.getenv('DB_NAME', 'news_db')
        charset = db_conf.get('charset', 'utf8mb4')

        logger.info(f"Connecting to DB: {host}:{port} ({database})")

        return mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset
        )
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        raise e