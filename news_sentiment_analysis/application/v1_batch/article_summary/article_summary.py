import configparser
import logging
import sys
from elasticsearch import Elasticsearch, helpers
from openai import OpenAI

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Config 로드 (Docker Volume 경로)
config_path = '/app/config/config.ini'
config = configparser.ConfigParser()
try:
    if not config.read(config_path):
        logger.error(f"Config file not found at {config_path}")
        sys.exit(1)
except Exception as e:
    logger.error(f"Failed to read config: {e}")
    sys.exit(1)

# 설정 변수 할당
try:
    ES_CONF = config['elasticsearch']
    # scheme://host:port 형식 조합
    ES_URL = f"{ES_CONF['scheme']}://{ES_CONF['host']}:{ES_CONF['port']}"
    SRC_INDEX = ES_CONF['source_index']
    DEST_INDEX = ES_CONF['dest_index']
    
    LLM_CONF = config['LLM']
    LLM_MODEL = LLM_CONF['model_name']
    LLM_TIMEOUT = float(LLM_CONF.get('timeout', 300))
    LLM_MAX_TOKENS = int(LLM_CONF.get('max_tokens', 512))

    BATCH_CONF = config['batch']
    BATCH_SIZE = int(BATCH_CONF.get('batch_size', 10))  # 저장 버퍼 크기
    SCAN_SIZE = int(BATCH_CONF.get('scan_size', 10))    # 읽기 청크 크기

except KeyError as e:
    logger.error(f"Missing config key: {e}")
    sys.exit(1)

# 클라이언트 초기화
es = Elasticsearch(ES_URL, request_timeout=60)
llm_client = OpenAI(
    base_url=LLM_CONF['api_base'],
    api_key=LLM_CONF['api_key'],
    timeout=LLM_TIMEOUT
)

def filter_unprocessed_docs(batch_docs):
    """
    배치 문서들의 ID를 타겟 인덱스에서 조회하여,
    이미 존재하는 문서는 제외하고 처리되지 않은 문서만 반환합니다.
    """
    if not batch_docs:
        return []
        
    ids = [d['_id'] for d in batch_docs]
    
    try:
        # mget을 사용하여 타겟 인덱스 조회 (_source=False로 성능 최적화) [web:40][web:48]
        response = es.mget(index=DEST_INDEX, ids=ids, _source=False, ignore=[404])
        
        # 인덱스가 아예 없으면(첫 실행) 404 무시하고 전체 처리
        if 'docs' not in response:
            return batch_docs

        unprocessed_docs = []
        # response['docs']는 요청한 ids 순서와 동일함
        for i, doc_status in enumerate(response['docs']):
            # found가 False인 (타겟에 없는) 문서만 골라냄
            if not doc_status.get('found', False):
                unprocessed_docs.append(batch_docs[i])
                
        if len(batch_docs) != len(unprocessed_docs):
            logger.info(f"Skipped {len(batch_docs) - len(unprocessed_docs)} already processed docs.")
            
        return unprocessed_docs

    except Exception as e:
        # 타겟 인덱스가 존재하지 않는 경우(최초 실행) 등 에러 발생 시 안전하게 전체 반환
        logger.warning(f"Existence check failed (assuming first run): {e}")
        return batch_docs

def generate_summary(text):
    """Custom LLM Endpoint 호출"""
    if not text:
        return ""
    # 입력 글자수 제한 
    SAFE_CHAR_LIMIT = 1200
    truncated_text = text[:SAFE_CHAR_LIMIT]

    try:
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are a skilled editor. "
                        "Summarize the news article in Korean. "
                        "Follow these rules strictly:\n"
                        "1. Summarize in exactly 3 bullet points.\n" # 3줄 개조식 강제
                        "2. Each point must be a complete sentence ending with a period.\n" # 문장 완결성 보장
                        "3. Total length must be under 300 characters.\n" # 길이 제약
                        "4. Do not include any introductory text like 'Here is the summary'." # 잡담 금지
                    )
                },
                {
                    "role": "user", 
                    "content": f"Article Content:\n{truncated_text}"
                }
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.3,
            stop=["4.", "\n\n\n", "User:"] 
        )
#        return response.choices[0].message.content
        summary = response.choices[0].message.content.strip()
        
        # 만약 결과가 중간에 잘렸는지(마침표로 안 끝나는지) 확인하는 후처리 로직
        if summary and not summary.endswith(('.', '!', '”', '"')):
             logger.warning("Summary truncated. Attempting to fix...")
             # 잘린 마지막 문장 제거 (가장 마지막 마침표까지만 살림)
             last_period_index = summary.rfind('.')
             if last_period_index != -1:
                 summary = summary[:last_period_index+1]
        
        return summary

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"First attempt failed: {error_msg}")
        
        # [재시도 로직] 에러 발생 시, 길이를 절반(600자)으로 줄이고 max_tokens도 200으로 줄여서 재시도
        if "maximum context length" in error_msg or "400" in error_msg:
            logger.info("Retrying with drastically shorter text...")
            try:
                shorter_text = text[:600] 
                response = llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "Summarize briefly."},
                        {"role": "user", "content": f"Summarize:\n\n{shorter_text}"}
                    ],
                    max_tokens=200 # 출력 공간도 축소
                )
                return response.choices[0].message.content
            except Exception as retry_e:
                logger.error(f"Retry failed: {retry_e}")
                return None
        return None

def main():
    if not es.ping():
        logger.error(f"Could not connect to Elasticsearch at {ES_URL}")
        return

    logger.info(f"Connected to ES at {ES_URL}")
    logger.info(f"Job: {SRC_INDEX} -> {DEST_INDEX} (Skip existing docs)")

    # Scroll(Scan) API 사용 - 전체 문서 순회
    scan_iter = helpers.scan(
        es,
        index=SRC_INDEX,
        query={"query": {"match_all": {}}},
        scroll="10m",
        size=SCAN_SIZE
    )

    buffer = []
    processed_count = 0

    for doc in scan_iter:
        buffer.append(doc)

        # 버퍼가 차면 처리 시작
        if len(buffer) >= BATCH_SIZE:
            # 1. 중복 체크 (Target 인덱스 조회)
            targets = filter_unprocessed_docs(buffer)
            
            # 2. 실제 요약 및 저장
            if targets:
                bulk_actions = []
                for target_doc in targets:
                    source = target_doc['_source']
                    content = source.get('content', '')
                    
                    summary = generate_summary(content)
                    if summary:
                        source['summary'] = summary
                        
                        action = {
                            "_index": DEST_INDEX,
                            "_id": target_doc['_id'],
                            "_source": source
                        }
                        bulk_actions.append(action)
                
                if bulk_actions:
                    helpers.bulk(es, bulk_actions)
                    processed_count += len(bulk_actions)
                    logger.info(f"Processed & Indexed {len(bulk_actions)} new docs.")
            
            buffer = []

    # 잔여 버퍼 처리
    if buffer:
        targets = filter_unprocessed_docs(buffer)
        if targets:
            bulk_actions = []
            for target_doc in targets:
                source = target_doc['_source']
                content = source.get('content', '')
                summary = generate_summary(content)
                if summary:
                    source['summary'] = summary
                    action = {
                        "_index": DEST_INDEX,
                        "_id": target_doc['_id'],
                        "_source": source
                    }
                    bulk_actions.append(action)
            
            if bulk_actions:
                helpers.bulk(es, bulk_actions)
                processed_count += len(bulk_actions)

    logger.info(f"Job Finished. Total newly processed: {processed_count}")

if __name__ == "__main__":
    main()

