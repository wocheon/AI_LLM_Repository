import os
import logging
from celery import shared_task
from openai import OpenAI
from datetime import datetime  
from utils.es_client import get_es_client
from utils.config_loader import config_loader

logger = logging.getLogger(__name__)

# [설정 로드]
# 전역 변수로 설정값만 로드 (Client 생성은 나중에)
try:
    llm_conf = config_loader.get_section('LLM')
    es_conf = config_loader.get_section('elasticsearch')

    API_KEY = llm_conf.get('api_key')
    API_BASE = llm_conf.get('api_base')
    MODEL_NAME = llm_conf.get('model_name', 'gpt-3.5-turbo')
    MAX_TOKENS = int(llm_conf.get('max_tokens', 300))
    TIMEOUT = int(llm_conf.get('timeout', 10))
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    API_KEY = None

def get_llm_client():
    """OpenAI 클라이언트 생성 (호출 시점 초기화)"""
    if not API_KEY:
        # Config 로드 실패 시 재시도
        conf = config_loader.get_section('LLM')
        key = conf.get('api_key')
        if not key:
            raise ValueError("API Key is missing in config.")
        return OpenAI(api_key=key, base_url=conf.get('api_base'), timeout=TIMEOUT)
    
    return OpenAI(
        api_key=API_KEY,
        base_url=API_BASE,
        timeout=TIMEOUT
    )

def _generate_summary_text(text):
    """실제 LLM 호출 로직 (내부 함수)"""
    try:
        # 1. 클라이언트 생성
        client = get_llm_client()
        
        # 2. 글자수 제한
        SAFE_CHAR_LIMIT = 1200
        truncated_text = text[:SAFE_CHAR_LIMIT]

        # 3. API 호출
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are a skilled editor. "
                        "Summarize the news article in Korean. "
                        "Follow these rules strictly:\n"
                        "1. Summarize in exactly 3 bullet points.\n"
                        "2. Each point must be a complete sentence ending with a period.\n"
                        "3. Total length must be under 300 characters.\n"
                        "4. Do not include any introductory text."
                    )
                },
                {
                    "role": "user", 
                    "content": f"Article Content:\n{truncated_text}"
                }
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"LLM Generation Failed: {e}")
        return None


@shared_task(name='tasks.summary.summarize_article', bind=True, max_retries=3)
def summarize_article(self, article_id):
    """
    [Task] 기사 원문을 ES에서 조회하여 요약하고 저장함.
    """
    logger.info(f"[Summary] Start processing article: {article_id}")
    
    # ES 연결
    es = get_es_client()
    org_index_name = es_conf.get('source_index', 'crawler_articles') 
    summary_index_name = es_conf.get('summary_index', 'article_summary') 
    
    try:
        # 1. ES 조회
        if not es.exists(index=org_index_name, id=article_id):
            logger.warning(f"Article {article_id} not found in ES.")
            return None

        res = es.get(index=org_index_name, id=article_id)
        source = res['_source']
        content = source.get('content', '')

        if not content:
            logger.warning(f"Article {article_id} has no content.")
            return None

        # 2. 요약 생성
        summary_text = _generate_summary_text(content)
        
        if not summary_text:
            logger.error(f"Failed to generate summary for {article_id}")
            # 재시도 (30초 딜레이)
            raise self.retry(countdown=30)

        # 3. ES 업데이트 (summary 필드 추가)
        new_doc = source.copy()  # 원본 데이터 복사
        new_doc['summary'] = summary_text  # 요약 필드 추가
        new_doc['processed_at'] = datetime.now().isoformat() # 처리 시간 추가 (선택)        

        es.index(
            index=summary_index_name,
            id=article_id,
            body=new_doc
        )
        logger.info(f"[Summary] Updated ES for {article_id}")

        # 4. 다음 단계(감성분석)를 위해 데이터 반환
        return {
            "id": article_id,
            "summary": summary_text
        }

    except Exception as e:
        logger.error(f"[Summary] Error processing {article_id}: {e}")
        # 예상치 못한 에러도 재시도
        raise self.retry(exc=e, countdown=60)
