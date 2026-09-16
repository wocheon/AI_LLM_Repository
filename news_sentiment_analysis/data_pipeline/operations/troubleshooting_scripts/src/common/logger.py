import logging
import sys
import os

def setup_logger(name: str, log_filename: str = None):
    """
    표준 로거 생성 함수
    :param name: 로거 이름 (예: 'Summarizer')
    :param log_filename: 로그 파일명 (예: 'summary.log'). None이면 파일 저장 안 함.
    :return: 설정된 logger 객체
    """
    # 1. 로그 디렉토리 자동 생성
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    # 2. 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 3. 핸들러 중복 방지 (기존 핸들러 제거)
    if logger.hasHandlers():
        logger.handlers.clear()
    
    logger.propagate = False  # 상위 로거로 전파 방지

    # 4. 포맷 설정
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 5. 콘솔 핸들러 (Stdout)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # 6. 파일 핸들러 (File)
    if log_filename:
        file_path = os.path.join(log_dir, log_filename)
        fh = logging.FileHandler(file_path, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    # 7. 외부 라이브러리 노이즈 제거 (너무 시끄러운 로그 억제)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger
