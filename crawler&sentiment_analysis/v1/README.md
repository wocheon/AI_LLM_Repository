# AI 모델을 활용한 기사 감성 분석용 아키텍쳐 (v1)

## 개요 
- 기사 수집 및 요약/감성분석을 제공하는 아키텍쳐를 구성
- 기사 요약에는 LLM을 활용하며 감성분석에는 KoBERT, KoELECTRA, Qwen3을 활용
- 각 모델별 감성 분석결과를 웹페이지를 통해 시각화 하여 제공

## 아키텍쳐 구성
```mermaid
graph TD
    %% 노드 정의
    RSS[Google News RSS]
    Crawler[Selenium/BS4 Crawler & Processor]
    MySQL[(MariaDB)]
    ES[(ElasticSearch)]
    LLM[OpenAI / LLM]
    Models[KoBERT / KoELECTRA / Qwen3]
    FASTAPI[FastAPI]
    request[Requests]
    Web[Flask Web Server]
    User[User]

    subgraph "Data"
        ES
        MySQL
    end
    
    %% 수집 및 즉시 처리 단계 (Sequential Processing)
    subgraph "Collection & Processing"
        RSS -->|1. 크롤링| Crawler
        Crawler --->|2. 메타데이터 저장| MySQL    
        Crawler --->|3. 본문 저장| ES
    end

    
    subgraph "AI Processing"
        subgraph "Summary"
            request -->|4. 요약 요청| LLM
            LLM -->|요약문 저장| ES
        end
        subgraph "Sentiment"
            FASTAPI -->|5. 감성 분석| Models
            Models -->|분석 결과 저장| MySQL            
        end
    end

    subgraph "Visualization"
        Web -..->|데이터 조회| ES & MySQL
        User -.->|접속| Web        
    end
    
```
- 특정 키워드 및 카테고리에 대한 기사를 수집하여 DB 및 ES에 저장
- LLM을 통해 기사 원문에 대한 요약 수행하여 별도 ES Index에 저장
- 감성분석을 통해 각 모델에 따른 기사의 긍정/부정/중립 여부를 확인
- DB 및 ES 내 저장된 결과를 토대로 Flask Web Server를 통해 사용자에게 시각화 제공


## 사용 기술 스택
- 크롤링: Selenium, BeautifulSoup4
- 데이터 저장: MariaDB, ElasticSearch
- LLM: OpenAI API ,vLLM
- 감성 분석 모델: KoBERT, KoELECTRA, Qwen3
- 웹 프레임워크: FastAPI, Flask
- 배포: Docker

