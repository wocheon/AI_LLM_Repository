import os
import logging
from celery import Celery

# 로깅 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 환경 변수 로드
BROKER_URL = os.getenv('BROKER_URL', 'redis://redis:6379/0')
RESULT_BACKEND = os.getenv('RESULT_BACKEND', 'redis://redis:6379/0')

# Celery 앱 초기화
# include 리스트에 분리된 태스크 모듈 경로를 지정합니다.
app = Celery(
    'news_worker',
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        'tasks.summary',   # tasks/summary.py
        'tasks.sentiment'  # tasks/sentiment.py
    ]
)

# Celery 추가 설정
app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Seoul',
    enable_utc=False,
    # 작업자 선점 방지 (장시간 작업 시 유용)
    task_acks_late=True,
    worker_prefetch_multiplier=1
)

if __name__ == '__main__':
    app.start()
