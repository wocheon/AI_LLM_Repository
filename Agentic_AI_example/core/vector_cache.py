# modules/vector_cache.py

### 설치 필요 패키지
#pip install chromadb sentence-transformers
# Ollama 임베딩 모델 사용 시
#python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

import chromadb
from chromadb.utils import embedding_functions
import uuid
import logging

logger = logging.getLogger(__name__)

class VectorCache:
    def __init__(self, persist_path="./chroma_data", threshold=0.3):
        self.threshold = threshold
        
        logger.info("📂 Vector DB (ChromaDB) 초기화 중...")
        
        self.client = chromadb.PersistentClient(path=persist_path)
        
        # 로컬 라이브러리 사용 (sentence-transformers)
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.collection = self.client.get_or_create_collection(
            name="chat_response_cache",
            embedding_function=self.emb_fn,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("✅ Vector DB 준비 완료")

    # [수정] intent 파라미터 추가 및 where 조건 적용
    def get(self, user_query, intent=None):
        try:
            # intent가 있으면 필터링, 없으면 전체 검색
            where_filter = {"intent": intent} if intent else None
            
            results = self.collection.query(
                query_texts=[user_query],
                n_results=1,
                where=where_filter  # [핵심] 메타데이터 필터링
            )
            
            if not results['ids'] or not results['distances'][0]:
                return None, None

            distance = results['distances'][0][0]
            cached_answer = results['metadatas'][0][0]['answer']

            if distance < self.threshold:
                logger.info(f"⚡ Cache Hit! (Dist: {distance:.4f}, Intent: {intent})")
                return cached_answer, distance
            else:
                return None, None
                
        except Exception as e:
            logger.error(f"Cache Get Error: {e}")
            return None, None

    # [수정] intent 파라미터 추가 및 메타데이터 저장
    def set(self, user_query, ai_answer, intent="UNKNOWN"):
        try:
            if len(ai_answer) < 5 or "오류" in ai_answer:
                return

            # 메타데이터에 intent 추가
            metadata = {"answer": ai_answer, "intent": intent}

            self.collection.add(
                ids=[str(uuid.uuid4())],
                documents=[user_query],
                metadatas=[metadata]
            )
            logger.info(f"💾 Cache Saved (Intent: {intent})")
        except Exception as e:
            logger.error(f"Cache Set Error: {e}")
    
    def clear(self):
        """캐시 전체 삭제"""
        try:
            self.client.delete_collection("chat_response_cache")
            # 삭제 후 재생성 (안 그러면 다음 호출 때 에러 남)
            self.collection = self.client.create_collection(
                name="chat_response_cache",
                embedding_function=self.emb_fn,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("🧹 Vector Cache Cleared")
        except Exception as e:
            logger.error(f"Cache Clear Error: {e}")