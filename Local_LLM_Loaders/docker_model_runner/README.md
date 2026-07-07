# Docker Model runner 

## 개요
- DMR(Docker Model Runner)을 통해 로컬 환경에서 LLM 모델을 사용하는 스크립트 예시 모음입니다.

## 구성 
```
📦docker_model_runner
 ┣ 📂manuals
 ┃ ┣ 📜docker_desktop_model.md
 ┃ ┗ 📜docker_desktop_model.txt
 ┣ 📂scirpts
 ┃ ┣ 📜config.ini
 ┃ ┣ 📜docker_model_interactive.py
 ┃ ┣ 📜docker_model_request_stats.py
 ┃ ┣ 📜docker_model_stream.py
 ┃ ┗ 📜docker_model_test.sh
 ┣ 📂text-to-sql
 ┃ ┣ 📜init.sql
 ┃ ┣ 📜mariadb.cnf
 ┃ ┣ 📜run_mariadb.sh
 ┃ ┣ 📜text-to-sql+chat+websearch.py
 ┃ ┣ 📜text-to-sql+chat.py
 ┃ ┗ 📜text-to-sql.py
 ┗ 📜README.md
 ```

## 구성요소 상세

### 📂manuals
#### 📜docker_desktop_model.md, 📜docker_desktop_model.txt

- docker desktop model runner 사용방법 


### 📂scirpts

#### 📜config.ini
- 분류 : `ini 파일`
- 스크립트에서 사용할 변수 목록
    - DMR API 연결 정보
    - 모델명 
    - SYSTEM Prompt : 응답 설정용 프롬프트
    - User Prompt : 실제 질문 사항

#### 📜docker_model_test.sh
- 분류 : `Bash 스크립트`
- curl 명령을 통한 LLM 호출용 스크립트 

#### 📜docker_model_request_stats.py
- 분류 : python 스크립트

- *requirements*
    - time
    - configparser
    - tiktoken
    - openai

- openai 라이브러리를 통해 LLM에 프롬프트를 보내고 응답을 받아 출력
- 해당 응답 건에 대한 통계수치를 출력


#### 📜docker_model_stream.py
- 분류 : `python 스크립트` (Python 3.12.3)

- *requirements*
    - time
    - configparser
    - tiktoken
    - openai

- openai 라이브러리를 통해 LLM에 프롬프트를 보내서 응답을 받음
- 스트리밍 방식을 통해 바로 응답을 출력하는 형태

#### 📜docker_model_interactive.py

- 분류 : `python 스크립트` (Python 3.12.3)

- *requirements*
    - time
    - configparser
    - tiktoken
    - sys
    - openai

- openai 라이브러를 통해 LLM에 프롬프트를 보내서 응답을 호출
- 대화형 챗봇 형태로 구성하여, 하나의 질문별로 응답 값을 스트리밍 방식으로 출력
- 이전 질문에 대해 후속 질문이 불가한 형태로 구성

- 후속 질문 테스트 결과
    ```
    질문(User) > 1+1은?
    --------------------------------------------------
    답변 (AI)  > 1+1은 2입니다.
    --------------------------------------------------
    ⏱️  8.17초 | 1.0 토큰/초 | 입력: 5, 출력: 8

    질문(User) > 위 값에 3을 더한 값은?
    --------------------------------------------------
    답변 (AI)  > 값을 주시하지 않아 결과를 알 수 없습니다.
    --------------------------------------------------
    ⏱️  8.55초 | 1.8 토큰/초 | 입력: 13, 출력: 15
    ```

#### 📜docker_model_interactive_history.py

- 분류 : `python 스크립트` (Python 3.12.3)

- *requirements*
    - time
    - configparser
    - tiktoken
    - sys
    - openai

- openai 라이브러를 통해 LLM에 프롬프트를 보내서 응답을 호출
- 대화형 챗봇 형태로 구성하여, 하나의 질문별로 응답 값을 스트리밍 방식으로 출력
- 이전 질문에 대해 후속 질문이 가능하도록 변경

- 후속 질문 테스트 결과
    ```
    질문(User) > 2+2는?
    --------------------------------------------------
    답변 (AI)  > 2+2 = 4.
    --------------------------------------------------
    ⏱️  8.30초 | 0.8 토큰/초 | 입력: 5, 출력: 7

    질문(User) > 위 값에 1을 더한 값은?
    --------------------------------------------------
    답변 (AI)  > 4+1 = 5.
    --------------------------------------------------
    ⏱️  8.08초 | 0.9 토큰/초 | 입력: 13, 출력: 7
    ```


### 📂text-to-sql 
- DMR <> MariaDB 연동 예시

### `MariaDB`
#### 📜init.sql 
- MariaDB docker Container 실행 후 자동실행되는 SQL 파일
- 전자 제품 재고 현황 테이블을 구성하도록 설정

#### 📜mariadb.cnf
- MariaDB 설정용 cnf 파일

#### 📜run_mariadb.sh
- MariaDB docker Container 실행 파일 

### `scripts`

### 📜text-to-sql.py
- LLM을 활용해 사용자 질문을 SQL로 변환하여 DB를 조회하고 답변해 주는 쇼핑몰 AI 에이전트

- 사용 예시
```
🛒 똑똑한 쇼핑몰 AI (Text-to-SQL) - 종료: quit
==================================================

질문 > 현재 갤럭시 s24의 재고현황에 대해 알려줘
🤔 SQL 생성 중...
   → 생성된 SQL: SELECT stock FROM products WHERE name LIKE '%Galaxy S24%';
🔍 DB 조회 중...
   [DEBUG] 실행할 쿼리: [SELECT stock FROM products WHERE name LIKE '%Galaxy S24%';]
   → 조회 결과: [{'stock': 42}]
🤖 최종 답변 생성 중...
--------------------------------------------------
AI: 갤럭시 S24의 현재 재고는 42개입니다.

| 제품명     | 브랜드 | 카테고리 | 수량 | 가격 |
|------------|--------|----------|------|------|
| 갤럭시 S24 | 삼성   | 스마트폰  | 42   | 1,199,000원 |
```


### 📜text-to-sql+chat.py
- SQL-Agent 기능에 일반 대화모드를 추가한 스크립트
- 질문에 따라 자동으로 동작을 구분하여 답변

- 사용예시 
```
🛒 Agentic 쇼핑몰 AI (Router + Self-Correction) - 종료: quit
============================================================

질문 > 1+1은?
🤔 의도 파악 중...
   → 일반 대화로 판단
------------------------------------------------------------
AI: 1+1은 2입니다. 😊

질문 > 남은 재고 중에 갤럭시는 어떤제품이 있지?
🤔 의도 파악 중...
   → DB 조회 필요
   [DEBUG] 실행할 쿼리: [SELECT name
FROM products
WHERE brand = 'Samsung' AND stock > 0]
   → 조회 성공! (3건)
------------------------------------------------------------
AI: 삼성 브랜드에서 남은 재고가 있는 제품은 갤럭시 S24, 갤럭시 S23, 갤럭시 북 S9입니다.

| 제품명         | 브랜드   | 카테고리 | 수량 | 가격       |
|----------------|----------|----------|------|------------|
| Galaxy S24     | Samsung  | 스마트폰 | 15   | 1,298,000원 |
| Galaxy S23     | Samsung  | 스마트폰 | 20   | 998,000원   |
| Galaxy Book S9 | Samsung  | 노트북   | 8    | 1,890,000원 |
```


### 📜text-to-sql+chat+websearch.py
- SQL-Agent + 일반대화모드 + Web검색 모드가 가능한 스크립트
- Web 검색 기능은 추가 수정 필요




