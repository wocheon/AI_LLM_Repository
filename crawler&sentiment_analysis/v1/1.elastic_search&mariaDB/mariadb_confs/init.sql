CREATE DATABASE IF NOT EXISTS crawler_sentiment_analysis;
USE crawler_sentiment_analysis;

# 유저 생성 
CREATE user IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'appuserpass';

-- 모든 권한을 부여 
GRANT ALL PRIVILEGES ON crawler_sentiment_analysis.* TO 'appuser'@'%';

-- 변경된 사항 적용 
FLUSH PRIVILEGES;

-- 키워드 테이블
CREATE TABLE IF NOT EXISTS crawler_keyword_list (
    id INT AUTO_INCREMENT PRIMARY KEY,
    keyword VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100)
)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;

INSERT INTO crawler_keyword_list (keyword, category) VALUES
('LLM', 'AI'),
('MaaS', 'AI'),
('쿠팡', '시사'),
('황사', '기후');


-- 기사 테이블
CREATE TABLE IF NOT EXISTS crawler_article_list (
    id INT AUTO_INCREMENT PRIMARY KEY,
    keyword_id INT,
    title VARCHAR(1024),
    content TEXT,
    url VARCHAR(2048) UNIQUE,
    published_at DATETIME,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;

-- 감성분석 결과 테이블
CREATE TABLE `sentiment_results` (
  `id` BIGINT(20) NOT NULL AUTO_INCREMENT COMMENT 'PK',
  `article_id` BIGINT(20) NOT NULL COMMENT '기사 원본 ID (FK)',
  `model_name` VARCHAR(50) NOT NULL COMMENT '모델명 (예: KoBERT, Qwen-2.5-3B)',
  `model_version` VARCHAR(20) DEFAULT NULL COMMENT '모델 버전 (예: v1.0, 2024-12-18)',
  `sentiment` VARCHAR(30) NOT NULL COMMENT '분석된 감정 (angry, happy 등)',
  `score` FLOAT NOT NULL COMMENT '확신도 점수 (0.0 ~ 1.0)',
  `inference_time_ms` INT(11) DEFAULT NULL COMMENT '추론 소요 시간 (ms) - 성능 모니터링용',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '분석 실행 일시',
  
  PRIMARY KEY (`id`),
  
  -- 성능 최적화를 위한 인덱스
  INDEX `idx_article_id` (`article_id`),  -- 기사별 조회용
  INDEX `idx_model_name` (`model_name`),  -- 모델별 통계용
  
  -- 중복 분석 방지 (한 기사를 같은 모델/버전으로 또 분석하는 것 방지)
  UNIQUE KEY `uk_article_model` (`article_id`, `model_name`, `model_version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='감성 분석 결과 통합 테이블';


--CREATE TABLE IF NOT EXISTS kobert_sentiment_analysis_result (
--    id INT AUTO_INCREMENT PRIMARY KEY,
--    article_id INT,
--    sentiment VARCHAR(20),
--    score FLOAT,
--    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
--)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;
--
--CREATE TABLE IF NOT EXISTS koelectra_sentiment_analysis_result (
--    id INT AUTO_INCREMENT PRIMARY KEY,
--    article_id INT,
--    sentiment VARCHAR(20),
--    score FLOAT,
--    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
--)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;
--
--
---- 결과 페이지 확인용 View 생성 - KoBERT
--
--create view kobert_sentiment_result_view 
--as
--select 
--A.id
--,A.keyword_id
--,B.keyword
--,A.title
--,A.content
--,A.url
--,C.sentiment as kobert_sentiment
--,C.score as kobert_score
--,A.published_at
--,A.collected_at
--from 
--	crawler_article_list A,
--	crawler_keyword_list B,
--	kobert_sentiment_analysis_result C
--where 
--	A.keyword_id = B.id
--	AND A.id = C.article_id;
--
--
---- 결과 페이지 확인용 View 생성 -  KoELECTRA
--
--create view koelectra_sentiment_result_view 
--as
--select 
--A.id
--,A.keyword_id
--,B.keyword
--,A.title
--,A.content
--,A.url
--,C.sentiment as koelectra_sentiment
--,C.score as koelectra_score
--,A.published_at
--,A.collected_at
--from 
--	crawler_article_list A,
--	crawler_keyword_list B,
--	koelectra_sentiment_analysis_result C
--where 
--	A.keyword_id = B.id
--	AND A.id = C.article_id;    
--
---- 결과 페이지 확인용 View 생성 - 모델 비교
--
--create view model_comparison_result_view 
--as
--SELECT 
--id, keyword_id, keyword, title, content, url,
--'KoELECTRA' AS model,
--koelectra_sentiment as sentiment, koelectra_score as score, published_at, collected_at
--FROM koelectra_sentiment_result_view
--UNION ALL
--SELECT 
--id, keyword_id, keyword, title, content, url,
--'KoBERT' AS model,
--kobert_sentiment as sentiment, kobert_score as score, published_at, collected_at
--FROM kobert_sentiment_result_view
--ORDER BY id, model;
