# Agentic_AI_example

간단한 의도 기반(Intent-aware) 캐시를 갖춘 컨텍스트-인식 AI 에이전트 예제입니다.  
이 저장소는 WSL(또는 리눅스) 환경에서 개발/실행된 것을 전제로 합니다.
최종 업데이트: 2023-12-08

---

## 요약 (Linux/WSL)
- 의도 분류(semantic routing)를 통한 DB / SEARCH / REVIEW / CHAT 모듈 선택
- 의미적 유사도 기반 Vector Cache 사용으로 응답 재사용
- chromadb 기반 벡터 저장소(chroma_data) 사용 (로컬 sqlite)
- **확장성**: 새로운 모듈 추가 용이

---

## 요구사항 및 설치 (Linux / WSL)
1. **Python 3.8+** (권장)
2. **가상환경 생성 및 활성화** (Linux/WSL)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
``` 

3. 환경변수/민감정보
- LLM API 키 등은 .env 또는 시스템 환경변수에 설정하세요.
- core/llm_client.py를 확인해 필요한 키 명칭을 확인합니다.

4. chroma_data
- chroma_data는 로컬 벡터 DB 파일을 포함합니다(chroma.sqlite3 등). 백업/복원 시 해당 디렉토리를 보존하세요.

---

## 실행
작업 디렉토리를 프로젝트 루트로 두고:
```bash
source .venv/bin/activate
python3 main.py
```
종료: `quit` 또는 `exit` 입력

---

## 사용 예시
- **일반 실행 (LLM 기반 의도 분류)**:
  - "재고가 얼마나 남았나요?" → LLM이 'DB' 모듈로 라우팅하여 재고 정보 조회
  - "최신 AI 기술 동향에 대해 알려줘" → LLM이 'SEARCH' 모듈로 라우팅하여 웹 검색 수행
  - "이 제품에 대한 다른 사람들의 평가는 어때?" → LLM이 'REVIEW' 모듈로 라우팅하여 리뷰 요약
  - "그냥 대화하고 싶어" → LLM이 'CHAT' 모듈로 라우팅하여 일반 대화
- **강제 라우팅 태그 사용 (특정 모듈 지정)**:
  - `[DB] 재고 문의` → 의도 분류 없이 'DB' 모듈 강제 실행
  - `[SEARCH] 챗GPT의 최신 업데이트는?`, `[REVIEW] 아이폰 15 후기 요약`, `[CHAT] 오늘 날씨 어때?` 등 동일 패턴으로 특정 모듈 지정 가능

---

## 파일/디렉토리 요약
### 현재 디렉토리 구성
```
.
├── README.md
├── config.py
├── main.py
├── requirements.txt
├── .venv/
├── chroma_data/
│   └── chroma.sqlite3
├── core/
│   ├── __init__.py
│   ├── history.py
│   ├── llm_client.py
│   └── vector_cache.py
├── log/
│   └── (로그 파일들)
└── modules/
    ├── __init__.py
    ├── chat_agent.py
    ├── db_agent.py
    ├── review_agent.py
    └── search_agent.py
```

### 각 파일별 상세 내용
- `config.py`: 애플리케이션 전반의 설정(로깅 레벨, LLM 모델명, 캐시 설정 등)을 정의합니다.
- `main.py`: 프로그램의 진입점으로, 사용자 입력을 받아 에이전트를 실행하는 인터랙티브 CLI를 제공합니다.
- `core/`: 핵심 로직을 포함하는 디렉토리입니다.
  - `llm_client.py`: LLM(Large Language Model)과의 통신을 담당하며, API 호출 및 응답 처리를 수행합니다.
  - `vector_cache.py`: 의미적 유사도 기반의 벡터 캐시를 구현하여, 이전에 처리된 요청에 대한 응답을 재사용합니다.
  - `history.py`: 사용자 대화 기록을 관리하여 컨텍스트를 유지합니다.
- `modules/`: 특정 의도에 따라 동작하는 에이전트 모듈들을 포함합니다.
  - `chat_agent.py`: 일반적인 대화 처리를 담당합니다.
  - `db_agent.py`: 데이터베이스 관련 질의(예: 재고 조회)를 처리합니다.
  - `review_agent.py`: 제품 리뷰 요약 등 리뷰 관련 작업을 수행합니다.
  - `search_agent.py`: 웹 검색 등 정보 검색 관련 작업을 처리합니다.
- `chroma_data/`: ChromaDB 벡터 데이터베이스 파일(예: `chroma.sqlite3`)이 저장되는 디렉토리입니다.
- `log/`: 애플리케이션 실행 중 발생하는 로그 파일들이 저장되는 디렉토리입니다. `config.py` 설정에 따라 로그가 생성됩니다.



---

## 주의사항
- 프로덕션 환경에서는 export 계정과 my.cnf 등 비밀정보 권한을 엄격히 관리하세요.
- chromadb 등 네이티브 의존성 또는 백엔드(예: faiss)가 필요한 경우 추가 설치가 필요합니다.
- LLM 호출 비용과 레이트리밋을 고려해 캐시/히트 비율을 튜닝하세요.
fig.py` 설정에 따라 로그가 생성됩니다.

---

## 주의사항
- 프로덕션 환경에서는 export 계정과 my.cnf 등 비밀정보 권한을 엄격히 관리하세요.
- chromadb 등 네이티브 의존성 또는 백엔드(예: faiss)가 필요한 경우 추가 설치가 필요합니다.
- LLM 호출 비용과 레이트리밋을 고려해 캐시/히트 비율을 튜닝하세요.