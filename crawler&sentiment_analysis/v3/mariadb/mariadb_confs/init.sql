CREATE DATABASE IF NOT EXISTS crawler_sentiment_analysis;
USE crawler_sentiment_analysis;

# 유저 생성 
CREATE user IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'appuserpass';

-- 모든 권한을 부여 
GRANT ALL PRIVILEGES ON crawler_sentiment_analysis.* TO 'appuser'@'%';

-- 변경된 사항 적용 
FLUSH PRIVILEGES;

CREATE TABLE `article_dataset` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `section` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `target` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '주요 분석 대상',
  `themes` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '관련 테마',
  `label_sentiment` int(11) DEFAULT NULL COMMENT '감성 라벨(0,1,2)',
  `confidence` float DEFAULT 0 COMMENT '모델 확신도(0~1)',
  `url` varchar(2048) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'ES Document ID',
  `summary_status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `embedding_status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'PENDING',
  `published_at` datetime DEFAULT NULL,
  `crawled_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `url` (`url`) USING HASH,
  UNIQUE KEY `unique_article` (`section`,`title`,`url`(255)) USING HASH
) ENGINE=InnoDB AUTO_INCREMENT=96580 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
