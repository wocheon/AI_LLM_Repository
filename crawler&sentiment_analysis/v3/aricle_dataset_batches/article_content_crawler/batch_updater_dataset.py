import random
import socket
import sys
import time
import logging
from datetime import datetime
from elasticsearch import Elasticsearch
import os

# 현재 파일이 있는 디렉토리를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils.db_util import get_db_conn

# crawler 모듈 import
from crawler import (
    get_driver,
    get_elasticsearch_client_from_config,
    collect_article_in_new_tab,
    collect_zombies,
    log_browser_and_tab_info,
    KSTFormatter,
    get_config,
    resolve_final_url_with_selenium
)

from utils.sqls_dataset import (
    UPDATE_PICK_TARGETS,
    SELECT_PICKED_TARGETS,
    UPDATE_COLLECT_SUCCESS,
    UPDATE_COLLECT_ERROR
)

# --- 로깅 설정 시작 (모든 모듈 로그 통합) ---
LOG_FILENAME = 'log/dataset_updater_2.log'
os.makedirs(os.path.dirname(LOG_FILENAME), exist_ok=True)

# 1. KST 포맷터 (기존 유지)
class KSTFormatter(logging.Formatter):
    KST_OFFSET = 9 * 3600
    def __init__(self, fmt=None, datefmt=None):
        if fmt is None: fmt = '%(asctime)s %(levelname)s %(message)s'
        super().__init__(fmt=fmt, datefmt=datefmt)
    def converter(self, timestamp):
        return time.gmtime(timestamp + self.KST_OFFSET)
    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt: return time.strftime(datefmt, ct)
        else: return time.strftime('%Y-%m-%d %H:%M:%S', ct) + f",{int(record.msecs):03d}"

# 2. 루트 로거 초기화 (중복 방지 핵심)
# 기존에 설정된 모든 핸들러 제거
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

# 3. 핸들러 새로 생성
file_handler = logging.FileHandler(LOG_FILENAME, encoding='utf-8')
file_handler.setFormatter(KSTFormatter())
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(KSTFormatter())

# 4. 루트 로거에 핸들러 등록
root.setLevel(logging.INFO)
root.addHandler(file_handler)
root.addHandler(stream_handler)

# 5. [중요] 외부 라이브러리 로그 끄기 (Noise Reduction)
logging.getLogger("elasticsearch").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)

# 6. 내 로거 생성
logger = logging.getLogger('dataset_updater')



def main():
    # 1. 워커 식별자 생성
    worker_id = f"worker_{socket.gethostname()}_{os.getpid()}"
    logger.info(f"Worker ID: {worker_id} 가동 시작")
    logger.info("=== [Article Dataset 통합 수집 배치 시작] ===")

    config = get_config("config.ini")

    # 2. 인프라 연결
    try:
        es = get_elasticsearch_client_from_config(config)
        conn = get_db_conn()
        cur = conn.cursor()
        logger.info("[INFO] ES/DB 연결 성공")
    except Exception as e:
        logger.error(f"[CRITICAL] 초기 연결 실패: {e}")
        return

    # 3. Driver 구동 (Undetected Chrome)
    driver = None
    try:
        driver = get_driver()
        logger.info("[INFO] Undetected Driver 구동 성공")
    except Exception as e:
        logger.error(f"[CRITICAL] 초기 드라이버 구동 실패: {e}")
        return

    # 통계 변수
    total_cnt = 0
    success_cnt = 0
    fail_cnt = 0

    try:
        # [Step 1] 작업 대상 선점
        logger.info("대상 선점 중 (PROCESSING 상태로 변경)...")
        cur.execute(UPDATE_PICK_TARGETS, (worker_id,))
        conn.commit()

        # [Step 2] 선점한 대상 조회
        cur.execute(SELECT_PICKED_TARGETS, (worker_id,))
        targets = cur.fetchall()
        total_cnt = len(targets)

        if total_cnt == 0:
            logger.info("수집할 대상이 없습니다. 종료합니다.")
            return

        logger.info(f"[INFO] 이번 턴 수집 대상: {total_cnt}건")

        # [Step 3] 개별 기사 처리 루프
        for idx, row in enumerate(targets, start=1):
            row_id, article_url, title, pub_dt, section, target_val, themes = row
            progress_pct = (idx / total_cnt) * 100

            # [변경] 지연 시간 대폭 단축 (기본 0.5 ~ 1.5초)
            # 이유: UC Driver와 TLS 우회 기술이 강력하므로 긴 대기는 불필요할 수 있음
            # 단, 연속 에러 발생 시에는 늘리는 로직 추가 권장
            if fail_cnt > 3 and idx % 5 == 0:
                 # 연속 실패가 많으면 잠시 쿨다운 (3~5초)
                 wait_time = random.uniform(3.0, 5.0)
                 logger.info(f"연속 실패 감지 -> 쿨다운: {wait_time:.2f}초...")
            else:
                 # 평소에는 빠르게 (0.5 ~ 1.2초)
                 wait_time = random.uniform(0.5, 1.2)

            # 로깅 레벨 조정 (너무 시끄러우면 debug로 변경하거나 생략)
            # logger.info(f"지연: {wait_time:.2f}초...")
            time.sleep(wait_time)

            logger.info(f"[{idx}/{total_cnt}] ({progress_pct:.1f}%) 작업 시작 - ID: {row_id}")

            # URL 정제 (Google News)
            final_url = article_url
            if "news.google.com" in article_url:
                try:
                    logger.info(" > 구글 뉴스 리다이렉션 해제 중...")
                    final_url = resolve_final_url_with_selenium(article_url, driver)
                    time.sleep(1.0)
                    logger.info(f" > 원문 URL 확보: {final_url}")
                except Exception as e:
                    logger.warning(f" > URL 정제 실패: {e}")
                    # 드라이버 재시작 시도
                    try:
                        if driver: driver.quit()
                        collect_zombies()
                        driver = get_driver()
                    except: pass

            # HTTPS 강제 변환
            if final_url and final_url.startswith("http://"):
                logger.info(" > HTTP -> HTTPS 변환")
                final_url = final_url.replace("http://", "https://")

            # 본문 수집
            content_clean = None
            try:
                # crawler.py 내부에서 로깅됨 (Trafilatura 성공, Newspaper 성공 등)
                content_clean = collect_article_in_new_tab(final_url, driver)
            except Exception as e:
                logger.error(f" [{idx}/{total_cnt}] !!! 추출 에러: {e}")
                # 에러 발생 시 드라이버 안전 재시작
                try:
                    if driver: driver.quit()
                except: pass
                collect_zombies()
                driver = get_driver()

            # 결과 처리
            if not content_clean:
                logger.warning(f" [{idx}/{total_cnt}] 실패: 본문 내용 없음 -> ERROR 기록")
                cur.execute(UPDATE_COLLECT_ERROR, (row_id,))
                conn.commit()
                fail_cnt += 1
                continue

            # Elasticsearch 저장
            es_id = None
            try:
                doc = {
                    "dataset_id": row_id,
                    "section": section,
                    "target": target_val,
                    "themes": themes,
                    "title": title,
                    "url": final_url,
                    "published_at": pub_dt.isoformat() if pub_dt else None,
                    "content": content_clean,
                    "crawled_at": datetime.now().isoformat(),
                    "source_table": "article_dataset",
                    "summary": None,
                    "summarized_at": None
                }
                res = es.index(index="dataset_articles", document=doc)
                es_id = res['_id']
            except Exception as e:
                logger.error(f" [{idx}/{total_cnt}] !!! ES 저장 오류: {e}")
                cur.execute(UPDATE_COLLECT_ERROR, (row_id,))
                conn.commit()
                fail_cnt += 1
                continue

            # DB 업데이트
            if es_id:
                try:
                    cur.execute(UPDATE_COLLECT_SUCCESS, (es_id, final_url, datetime.now(), row_id))
                    conn.commit()
                    success_cnt += 1
                    logger.info(f" [{idx}/{total_cnt}] 완료: DB/ES 저장 성공 (ID: {row_id})")
                except Exception as e:
                    logger.error(f" [{idx}/{total_cnt}] !!! DB 업데이트 오류: {e}")
                    fail_cnt += 1

            time.sleep(1.0)

    finally:
        try:
            if driver: driver.quit()
        except:
            pass
        collect_zombies()
        if cur: cur.close()
        if conn: conn.close()

        logger.info("="*40)
        logger.info(f" [수집 결과 요약]")
        logger.info(f" - 처리 대상: {total_cnt} 건")
        logger.info(f" - 성공 건수: {success_cnt} 건")
        logger.info(f" - 실패 건수: {fail_cnt} 건")
        logger.info("="*40)
        logger.info("=== [통합 수집 배치 종료] ===")


if __name__ == "__main__":
    main()

