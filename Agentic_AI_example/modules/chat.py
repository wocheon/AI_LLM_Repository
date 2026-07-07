# modules/chat.py
import config
from core.llm_client import get_client

client = get_client()

def simple_chat(user_input, context_messages=None):
    """
    [CHAT] 일반 대화 (컨텍스트 지원)
    :param user_input: 사용자 현재 질문
    :param context_messages: 이전 대화 기록 리스트 (선택)
    """
    try:

        system_instruction = """
        You are a concise and helpful AI assistant.
        
        [Guidelines]
        1. Answer in Korean naturally.
        2. Be concise: Keep answers short (1-3 sentences) unless a long explanation is requested.
        3. Avoid repetitive greetings or filler words.
        4. Get straight to the point.
        """

        # 기본 시스템 메시지
        messages = [
            {"role": "system", "content": system_instruction}
        ]
        
        # [핵심] 이전 대화 기록이 있다면 추가 (Context Injection)
        if context_messages:
            messages.extend(context_messages)
            
        # 현재 질문 추가
        messages.append({"role": "user", "content": user_input})

        stream = client.chat.completions.create(
            model=config.SMART_MODEL_NAME,
            messages=messages,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        yield f"대화 오류: {e}"
