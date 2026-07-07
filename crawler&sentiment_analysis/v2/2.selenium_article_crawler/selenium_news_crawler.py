import configparser
import feedparser
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from newspaper import Article
import trafilatura
import requests
import time
import os
import psutil
import logging
import sys
from celery import Celery, chain, group

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service

from elasticsearch import Elasticsearch, exceptions as es_exceptions

import db_util   # keyword 조회/DB 저장용
# from sqls import SELECT_ALL_KEYWORDS, INSERT_ARTICLE 
# 수정: SELECT_ALL_KEYWORDS는 아래에서 직접 정의, INSERT_ARTICLE만 import
from sqls import INSERT_ARTICLE, SELECT_ALL_KEYWORDS

# ----- 로깅 설정 -----
LOG_FILENAME = 'log/crawler.log'
BROKER_URL = os.getenv('BROKER_URL', 'redis://redis:6379/0')
celery_app = Celery('producer', broker=BROKER_URL)

class KSTFormatter(logging.Formatter):
    KST_OFFSET = 9 * 3600  # UTC+9시간

    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
            fmt = '%(asctime)s %(levelname)s %(message)s'
        super().__init__(fmt=fmt, datefmt=datefmt)

    def converter(self, timestamp):
        return time.gmtime(timestamp + self.KST_OFFSET)

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            return time.strftime(datefmt, ct)
        else:
            t = time.strftime('%Y-%m-%d %H:%M:%S', ct)
            return f"{t},{int(record.msecs):03d}"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False

file_handler = logging.FileHandler(LOG_FILENAME, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(KSTFormatter())

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(KSTFormatter())

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


#--- Chrome 브라우저 및 탭 수 로깅용 함수 ---
def log_browser_and_tab_info(driver, logger=None):
    if logger is None:
        logger = logging.getLogger(__name__)
    chrome_count = 0
    chromedriver_count = 0
    try:
        for proc in psutil.process_iter(['name']):
            pname = proc.info['name']
            if pname:
                pname_lower = pname.lower()
                if 'chrome' in pname_lower and 'chromedriver' not in pname_lower:
                    chrome_count += 1
                if 'chromedriver' in pname_lower:
                    chromedriver_count += 1
        logger.info(f"[PROCESS MONITOR] 실행 중 chrome 프로세스: {chrome_count}, chromedriver 프로세스: {chromedriver_count}")
    except Exception as e:
        logger.warning(f"[PROCESS MONITOR] 프로세스 조회 실패: {e}")
    
    try:
        tab_count = len(driver.window_handles) if driver else 0
        logger.info(f"[SELENIUM] 현재 열린 탭(윈도우) 수: {tab_count}")
    except Exception as e:
        logger.warning(f"[SELENIUM] 탭 수 조회 실패: {e}")


# ----- 설정 읽는 함수 -----
def get_config(path="config.ini"):
    config = configparser.ConfigParser()
    config.read(path)
    return config

def get_driver():
    options = Options()
    options.binary_location = "/opt/chrome/chrome-headless-shell"
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--lang=ko_KR')
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-plugins')
    options.add_argument('--mute-audio')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--remote-allow-origins=*')
    options.add_argument('--window-size=1920,1080')

    base_path = os.path.dirname(__file__)
    driverLog_path = os.path.join(base_path, 'log', 'chromedriver.log')
    
    service = Service(
        executable_path='/usr/local/bin/chromedriver',
        service_args=[
            "--verbose",
            f"--log-path={driverLog_path}"
        ]
    )

    options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(15)
    return driver


def get_elasticsearch_client_from_config(config):
    escfg = config['elasticsearch']
    host = escfg['host']
    port = int(escfg.get('port', 9200))
    scheme = escfg.get('scheme', 'http')
    user = escfg.get('user')
    password = escfg.get('password')
    es_kwargs = {
        "host": host,
        "port": port,
        "scheme": scheme
    }
    if user and password:
        es = Elasticsearch([es_kwargs], basic_auth=(user, password))
    else:
        es = Elasticsearch([es_kwargs])
    if not es.ping():
        raise ConnectionError(f"Elasticsearch 서버가 {host}:{port} 에서 응답하지 않습니다.")
    return es


def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def extract_with_bs4(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        selectors = [
            "div.article-body", "div#article_body", "div.text",
            "article", "section", "main"
        ]

        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text

        text = soup.get_text(separator=" ", strip=True)
        if len(text) > 100:
            return text
    except Exception as e:
        logger.warning(f'[bs4] 본문 추출 실패: {e}')
    return None


def wait_for_any_element(driver, selectors, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        for selector in selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                if elems:
                    return selector
            except Exception:
                continue
        time.sleep(0.5)
    raise TimeoutException("None of the selectors were found in time.")


def extract_news_content(url, driver=None):
    # 1) trafilatura
    try:
        downloaded = trafilatura.fetch_url(url)
        content = trafilatura.extract(downloaded)
        if content and len(content.strip()) > 100:
            logger.info("[본문] trafilatura 추출 성공")
            return content.strip()
    except Exception as e:
        logger.warning(f"[본문] trafilatura 실패: {e}")

    # 2) newspaper3k
    try:
        a = Article(url, language='ko')
        a.download()
        a.parse()
        if a.text and len(a.text.strip()) > 100:
            logger.info("[본문] newspaper3k 추출 성공")
            return a.text.strip()
    except Exception as e:
        logger.warning(f"[본문] newspaper3k 실패: {e}")

    # 3) bs4
    text = extract_with_bs4(url)
    if text:
        logger.info("[본문] requests+BeautifulSoup 추출 성공")
        return text

    # 4) selenium fallback
    if driver:
        try:
            selectors = ["div.article-body", "div#article_body", "div.text"]
            try:
                wait_for_any_element(driver, selectors + ["article", "main", "section"], timeout=10)
            except TimeoutException:
                logger.warning("[SELENIUM] 주요 본문 셀렉터 대기 타임아웃")

            for sel in selectors:
                if driver.find_elements(By.CSS_SELECTOR, sel):
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    text = el.text.strip()
                    if len(text) > 50:
                        logger.info(f"[본문] {sel} 커스텀 셀렉터 추출 성공")
                        return text

            for tag in ["article", "main", "section"]:
                els = driver.find_elements(By.TAG_NAME, tag)
                if els:
                    text = els[0].text.strip()
                    if len(text) > 50:
                        logger.info(f"[본문] <{tag}> 태그 기반 추출 성공")
                        return text
        except Exception as e:
            logger.warning(f"[본문] selenium 본문 추출 실패: {e}")

    logger.info("[본문] 본문 추출 실패")
    return None


def resolve_final_url_with_selenium(url, driver=None, retries=2, wait_seconds=4):
    owns_driver = False
    if driver is None:
        driver = get_driver()
        owns_driver = True

    connection_pool_error_count = 0

    for i in range(retries):
        try:
            driver.get(url)
            time.sleep(wait_seconds)
            final_url = driver.current_url
            logger.info(f"[SELENIUM] 최종 원문 URL: {final_url}")
            return final_url
        except Exception as e:
            error_msg = str(e)
            if 'ConnectionPool' in error_msg and 'Read timed out' in error_msg:
                connection_pool_error_count += 1
                logger.warning(f"[SELENIUM] ConnectionPool/ReadTimedOut 오류 ({connection_pool_error_count}/2): {e}, url: {url}")
                if connection_pool_error_count >= 2:
                    logger.warning("[SELENIUM] ConnectionPool 오류 2회 발생, 드라이버 재시작 수행")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    collect_zombies()
                    driver = get_driver()
                    connection_pool_error_count = 0
                    continue
            elif isinstance(e, TimeoutException):
                logger.warning(f"[SELENIUM] Timeout 발생 ({i+1}/{retries}), url: {url} - {e}")
            elif isinstance(e, WebDriverException):
                logger.warning(f"[SELENIUM] WebDriver 예외: {e}, url: {url}")
            else:
                logger.warning(f"[SELENIUM] 기타 예외({i+1}/{retries}): {e}, url: {url}")

    logger.warning(f"[SELENIUM] 모든 재시도 실패, 드라이버 재시작 시도 및 URL resolve 재시도: {url}")
    try:
        driver.quit()
    except Exception:
        pass
    collect_zombies()
    driver = get_driver()

    try:
        driver.get(url)
        time.sleep(wait_seconds)
        final_url = driver.current_url
        logger.info(f"[SELENIUM] 재시작 후 최종 원문 URL: {final_url}")
        return final_url
    except Exception as e:
        logger.error(f"[SELENIUM] 재시작 후에도 실패: {e}, url: {url}")

    if owns_driver:
        try:
            driver.quit()
        except Exception:
            pass
        collect_zombies()
    return url


def get_real_article_url(entry_link, driver=None):
    if "news.google.com" in entry_link:
        parsed = urllib.parse.urlparse(entry_link)
        params = urllib.parse.parse_qs(parsed.query)
        url_list = params.get('url')
        if url_list and url_list[0].startswith("http"):
            return url_list[0]
        return resolve_final_url_with_selenium(entry_link, driver=driver)
    else:
        return entry_link


def get_rss_entry_summary(entry):
    candidates = []
    if 'summary' in entry and entry.summary:
        candidates.append(entry.summary)
    if 'description' in entry and entry.description:
        candidates.append(entry.description)
    if 'content' in entry and entry.content:
        for c in entry.content:
            val = c.get('value')
            if val:
                candidates.append(val)
    for item in candidates:
        cleaned = clean_html(item)
        if cleaned and len(cleaned) > 30:
            return cleaned.strip()
    return "[RSS 내용 없음]"


def collect_zombies():
    try:
        while True:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            else:
                logger.info(f"[ZOMBIE] 자식 프로세스 {pid} 수거")
    except ChildProcessError:
        pass


def collect_article_in_new_tab(article_url, driver):
    original_handle = driver.current_window_handle
    driver.execute_script(f"window.open('{article_url}');")
    driver.switch_to.window(driver.window_handles[-1])

    content = None
    try:
        content = extract_news_content(article_url, driver)
    except Exception as e:
        logger.warning(f"[collect_article_in_new_tab] 추출 실패: {e}")

    driver.close()
    driver.switch_to.window(original_handle)
    return content


def main():
    logger.info("=== [크롤러 시작] ===")
    config = get_config("config.ini")

    crawlercfg = config['crawler']
    articlecnf = int(crawlercfg.get('article_cnt_by_keyword', 1))

    try:
        es = get_elasticsearch_client_from_config(config)
        logger.info("[INFO] Elasticsearch 연결 성공")
    except Exception as e:
        logger.error(f"[ERROR] Elasticsearch 연결 실패: {e}")
        return

    conn = db_util.get_db_conn()
    cur = conn.cursor()
    try:
        # [수정 2] category 포함된 쿼리 실행
        cur.execute(SELECT_ALL_KEYWORDS)
        keywords = cur.fetchall()
        logger.info(f"[INFO] 키워드 조회: {len(keywords)}건")
    except Exception as e:
        logger.error(f"[DB] 키워드 조회 오류: {e}")
        cur.close()
        conn.close()
        return    

    logger.info(f"[INFO] 키워드 별 기사 수집 개수 제한: {articlecnf}건")

    driver = get_driver()
    try:
        # [수정 3] unpacking 시 category 변수 추가
        for kid, kw, category in keywords:
            
            # [수정 4] 검색어 조합 및 URL 인코딩 (키워드 + 카테고리)
            if category:
                search_query = f"{kw} {category}"
            else:
                search_query = kw
                
            logger.info(f"\n[LOOP] 키워드: {kw} (ID: {kid}) / 카테고리 필터: {category if category else 'None'}")
            log_browser_and_tab_info(driver, logger)  
            
            # 한글/공백 처리를 위해 URL 인코딩 필수
            encoded_query = urllib.parse.quote(search_query)
            
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(url)

            if not feed.entries:
                logger.warning(f"[WARNING] 피드 결과 없음: {search_query}")
                continue

            for entry in feed['entries'][:articlecnf]:
                pub_dt = None
                if 'published_parsed' in entry and entry['published_parsed']:
                    pub_dt = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')

                entry_title = entry.get('title', '').strip()
                entry_link = entry.get('link', '').strip()
                logger.info(f"[ENTRY] {entry_title}")
                logger.info(f" RSS 링크: {entry_link}")

                article_url = get_real_article_url(entry_link, driver=driver)
                logger.info(f" 원문 URL: {article_url}")

                content_clean = None
                try:
                    content_clean = collect_article_in_new_tab(article_url, driver)
                except Exception as e:
                    logger.error(f"[ERROR] 본문 추출 중 에러: {e}, URL: {article_url}")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    collect_zombies()
                    driver = get_driver()
                    logger.info("[INFO] 드라이버 재생성 후 재시도")
                    try:
                        content_clean = collect_article_in_new_tab(article_url, driver)
                    except Exception as e2:
                        logger.error(f"[ERROR] 재시도 중 에러: {e2}, URL: {article_url}")

                if not content_clean:
                    logger.info("[INFO] 본문 추출 실패, RSS summary 대체 사용")
                    content_clean = get_rss_entry_summary(entry)

                preview = (content_clean[:200] + '...') if len(content_clean) > 200 else content_clean
                logger.info(f" 본문 일부: {preview}")

                doc = {
                    "keyword_id": kid,
                    "keyword": kw,
                    "category": category,  # [선택] ES에도 카테고리 정보 함께 저장하면 좋음
                    "title": entry_title,
                    "url": article_url,
                    "published_at": pub_dt,
                    "content": content_clean,
                    "crawled_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                es_id = None
                try:
                    res = es.index(index="crawler_articles", document=doc)
                    es_id = res['_id']
                    es.indices.refresh(index="crawler_articles")
                    logger.info(f"[Elasticsearch] 인덱싱 성공, id: {es_id}")
                except es_exceptions.ConnectionError as e:
                    logger.error(f"[Elasticsearch 오류] 연결 실패: {e}")
                except Exception as e:
                    logger.error(f"[Elasticsearch 오류]: {e}")

                db_content = es_id if es_id else "[no_es_id]"
                try:
                    cur.execute(INSERT_ARTICLE, (
                        kid,
                        entry_title,
                        db_content,
                        article_url,
                        pub_dt
                    ))
                    conn.commit()
                    logger.info("[DB] 저장 완료")
                                                            
                except Exception as e:
                    logger.error(f"[DB] Insert error: {e}, URL: {article_url}")
                    if es_id:
                        try:
                            es.delete(index="crawler_articles", id=es_id)
                            logger.info(f"[Elasticsearch] DB 저장 실패로 삭제한 문서 id: {es_id}")
                        except Exception as del_e:
                            logger.error(f"[Elasticsearch] 문서 삭제 실패: {del_e}")

                if es_id:
                    try:
                        # 태스크 이름 변수화 (오타 방지)
                        TASK_SUMMARY = 'tasks.summary.summarize_article'
                        TASK_SENTIMENT = 'tasks.sentiment.analyze_sentiment'

                        kobert_sentiment_config = {"model_name": "kobert","model_version": "v1.0", "api_url": "http://sentiment_model_fastapi:8000/predict/kobert/batch"}
                        koelectra_sentiment_config = {"model_name": "koelectra","model_version": "v1.0", "api_url": "http://sentiment_model_fastapi:8000/predict/koelectra/batch"}
                        qwen3_sentiment_config = {"model_name": "qwen3","model_version": "v1.0", "api_url": "http://sentiment_model_fastapi:8000/predict/llm/batch"}

                        logger.info(f"-> Sending to Celery: {es_id}")
                        
                        pipeline = chain(
                            celery_app.signature(TASK_SUMMARY, args=[es_id]),
                            group(
                                celery_app.signature(TASK_SENTIMENT, args=[kobert_sentiment_config]),
                                celery_app.signature(TASK_SENTIMENT, args=[koelectra_sentiment_config]),
                                celery_app.signature(TASK_SENTIMENT, args=[qwen3_sentiment_config])
                            )
                        )
                        res = pipeline.apply_async()
                        logger.info(f"-> Triggered analysis pipeline for {es_id} (ID: {res.id})")
                        
                    except Exception as ce:
                        logger.error(f"[Celery Error] {ce}")
                else:
                    logger.warning(f"Skipping Celery: No ES ID for {article_url}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        collect_zombies()
        cur.close()
        conn.close()
        logger.info("=== [크롤러 종료] ===")

if __name__ == "__main__":
    main()

