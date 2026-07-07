# config.py
import pymysql

# --- 로깅 설정 ---
LOG_TO_CONSOLE = True   # 터미널 출력 여부
LOG_TO_FILE = True      # 파일 저장 여부
LOG_FILE_NAME = 'log/app.log'
LOG_LEVEL = 'INFO'      # DEBUG, INFO, WARNING, ERROR

# --- 데이터베이스 설정 ---
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'rootpass',
    'db': 'shop',
    'charset': 'utf8mb4',
    'init_command': 'SET NAMES utf8mb4 COLLATE utf8mb4_general_ci',
    'cursorclass': pymysql.cursors.DictCursor
}

# --- LLM API 설정 ---
DMR_BASE_URL = "http://localhost:12434/engines/llama.cpp/v1"
DMR_API_KEY = "ollama"

# [변경] 모델 이원화
# 1. 고성능 모델 (분석, 요약, 대화용)
SMART_MODEL_NAME = "ai/qwen3:4B-UD-Q8_K_XL"

# 2. 초고속 경량 모델 (라우팅, 분류, 단순작업용)
# (사용자 환경에 qwen2.5:0.5b 또는 llama3.2:1b 등이 설치되어 있어야 함. 없다면 SMART_MODEL과 같게 설정)
#FAST_MODEL_NAME = "ai/gemma3:4B-Q4_K_M"
FAST_MODEL_NAME = "ai/qwen3:4B-UD-Q4_K_XL"

