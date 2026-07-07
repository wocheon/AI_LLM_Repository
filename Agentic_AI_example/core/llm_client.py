# llm_client.py
import time
import logging
from openai import OpenAI
import config

logger = logging.getLogger("LLM_Client")

class LoggingClient:
    """OpenAI 클라이언트 래퍼 (로깅 기능 추가)"""
    def __init__(self, base_url, api_key):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.chat = self.Chat(self.client.chat)

    class Chat:
        def __init__(self, chat_client):
            self.completions = self.Completions(chat_client.completions)

        class Completions:
            def __init__(self, completions_client):
                self.create_fn = completions_client.create

            def create(self, **kwargs):
                model = kwargs.get('model', 'unknown')
                messages = kwargs.get('messages', [])
                stream = kwargs.get('stream', False)
                
                # 1. [요청 로그]
                # (너무 길면 시스템 프롬프트는 생략하고 유저 질문만 보여줄 수도 있음)
                user_msg = next((m['content'] for m in messages if m['role'] == 'user'), "No user msg")
                logger.info(f"🚀 [LLM Start] Model: {model} | User: {user_msg[:50]}...")
                
                start_time = time.time()
                
                try:
                    # 실제 API 호출
                    response = self.create_fn(**kwargs)
                    
                    # 2. [응답 로그] - 스트리밍 여부에 따라 다름
                    duration = time.time() - start_time
                    
                    if stream:
                        logger.info(f"✅ [LLM Stream Init] Model: {model} ({duration:.2f}s)")
                        # 스트리밍은 제너레이터를 반환하므로 여기서 내용을 찍을 순 없음 (찍으려면 래핑 필요)
                        return response
                    else:
                        # 일반 응답
                        content = response.choices[0].message.content
                        logger.info(f"✅ [LLM Done] Model: {model} ({duration:.2f}s) | Output: {content[:50]}...")
                        return response
                        
                except Exception as e:
                    logger.error(f"❌ [LLM Error] Model: {model} | Error: {e}")
                    raise e

def get_client():
    try:
        # 래퍼 클래스 반환
        return LoggingClient(base_url=config.DMR_BASE_URL, api_key=config.DMR_API_KEY)
    except Exception as e:
        logger.error(f"Client Init Failed: {e}")
        raise e
