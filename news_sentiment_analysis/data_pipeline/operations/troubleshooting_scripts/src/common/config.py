import configparser
import os
import sys

def load_config(path: str = 'config.ini') -> configparser.ConfigParser:
    """
    설정 파일 로드 및 유효성 검사
    :param path: config.ini 파일 경로
    :return: ConfigParser 객체
    """
    # 1. 파일 존재 여부 확인
    if not os.path.exists(path):
        # 실행 위치 기준 절대 경로 확인 (디버깅용)
        abs_path = os.path.abspath(path)
        print(f"❌ [Error] 설정 파일을 찾을 수 없습니다.")
        print(f"   - 경로: {abs_path}")
        print(f"   - 실행 위치: {os.getcwd()}")
        sys.exit(1)

    # 2. 설정 로드
    config = configparser.ConfigParser()
    try:
        read_files = config.read(path, encoding='utf-8')
        if not read_files:
            raise FileNotFoundError(f"파일을 읽을 수 없습니다: {path}")
            
    except Exception as e:
        print(f"❌ [Error] 설정 파일 파싱 실패: {e}")
        sys.exit(1)

    return config
