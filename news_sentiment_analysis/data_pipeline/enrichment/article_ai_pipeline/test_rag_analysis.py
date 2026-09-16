import asyncio
import argparse
from openai import AsyncOpenAI

from src.common.config import load_config
from src.common.es_client import get_es_client
from src.common.logger import setup_logger

logger = setup_logger("RAG_Tester")

async def get_embedding(client, model, text):
    """입력 텍스트 벡터화"""
    try:
        response = await client.embeddings.create(input=text, model=model)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        return None

async def search_similar_articles(es, index_name, vector, top_k=3):
    """ES 벡터 검색 (KNN)"""
    res = await es.search(
        index=index_name,
        knn={
            "field": "context_vector",
            "query_vector": vector,
            "k": top_k,
            "num_candidates": 100
        },
        _source=["title", "summary", "target", "sentiment_label", "themes", "published_at"]
    )
    return res['hits']['hits']

async def analyze_with_llm(client, model, target_article, context_articles):
    """LLM 분석 요청 (RAG 기반 예측)"""
    
    # 1. 컨텍스트 구성
    context_text = ""
    for i, hit in enumerate(context_articles, 1):
        doc = hit['_source']
        sentiment_map = {0: "중립", 1: "부정(Bad)", 2: "긍정(Good)"}
        sentiment_str = sentiment_map.get(doc.get('sentiment_label', 0), "중립")
        context_text += f"[{i}] {doc.get('title')} -> {sentiment_str}\n"

    # 2. 프롬프트 작성 (Strict Format & Korean Only)
    system_prompt = (
        "You are an AI Market Predictor. Analyze the 'New Article' based on 'Past Cases'.\n"
        "Output MUST be a single line in this format: `Target | Prediction | Confidence | Reason Summary`\n"
        "- Prediction: 2 (Positive), 1 (Negative), 0 (Neutral)\n"
        "- Confidence: 0.0 ~ 1.0 (based on similarity with past cases)\n"
        "- Reason Summary: Explain in KOREAN (under 15 words) referencing past cases."
    )
    
    user_prompt = f"""
    [Past Cases]
    {context_text}

    [New Article]
    Title: {target_article['title']}
    Target: {target_article['target']}
    Summary: {target_article['summary']}

    Output Format: `Target | Prediction | Confidence | Reason Summary`
    """

    # 3. LLM 호출
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0
    )
    return response.choices[0].message.content.strip()

async def main():
    parser = argparse.ArgumentParser(description="RAG Analysis Tester")
    parser.add_argument('--config', default='config.ini')
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    # ==========================================
    # [입력 데이터] 파이프라인 처리 결과라고 가정
    # ==========================================
    target_article = {
        "title": "삼성전자, HBM 공급 계약 체결 소식에 주가 강세",
        "summary": "1. 삼성전자가 엔비디아와 차세대 HBM 공급 계약을 맺었다는 보도가 나왔다.\n2. 이에 따라 오전 장에서 주가가 3% 이상 상승 중이다.\n3. 반도체 업황 회복에 대한 기대감이 커지고 있다.",
        "target": "삼성전자",
        "themes": "수주/공급계약"
    }

    print("="*60)
    print(f"📰 [New Article Input]")
    print(f"Title : {target_article['title']}")
    print(f"Target: {target_article['target']}")
    print(f"Summary:\n{target_article['summary']}")
    print("="*60)

    # 1. 클라이언트 설정
    es = get_es_client(config)
    
    # 임베딩용
    emb_conf = config['embedding_model']
    emb_client = AsyncOpenAI(
        base_url=emb_conf.get('base_url').replace("/v1", "") + "/v1",
        api_key='ollama'
    )
    
    # 분석용 LLM
    llm_conf = config['llm_model']
    llm_client = AsyncOpenAI(
        base_url=llm_conf.get('base_url'),
        api_key=llm_conf.get('api_key')
    )

    try:
        # 2. 임베딩 생성 (Title + Summary 결합)
        logger.info("🧬 벡터 생성 중...")
        text_for_vector = f"{target_article['title']}\n{target_article['summary']}"
        vector = await get_embedding(emb_client, emb_conf['model'], text_for_vector)
        
        if not vector:
            print("❌ 벡터 생성 실패")
            return

        # 3. 유사 기사 검색 (RAG Context)
        logger.info("🔍 유사 기사 검색 중 (Context Retrieval)...")
        index_name = config['elasticsearch']['source_index']
        hits = await search_similar_articles(es, index_name, vector)
        
        print(f"\n📚 [Retrieved Context: {len(hits)} articles]")
        for h in hits:
            s = h['_source']
            sentiment = {0: "⚪", 1: "🔴", 2: "🔵"}.get(s.get('sentiment_label', 0), "⚪")
            print(f"- {sentiment} [{h['_score']:.4f}] {s.get('title')} ({s.get('target')})")

        if not hits:
            print("⚠️ 유사한 기사가 없습니다.")
            return

        # 4. LLM 분석 결과 출력 부분 (main 함수 내부)
        logger.info("🧠 AI 예측 분석 중...")
        analysis = await analyze_with_llm(llm_client, llm_conf['model'], target_article, hits)
        
        print("\n" + "="*80)
        print(f"📰 기사 제목: {target_article['title']}")
        print("-" * 80)
        print(f"🤖 AI 분석결과: {analysis}")
        print("="*80)

    finally:
        await es.close()
        await emb_client.close()
        await llm_client.close()

if __name__ == "__main__":
    asyncio.run(main())
