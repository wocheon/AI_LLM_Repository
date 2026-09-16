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

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
#import chromedriver_autoinstaller
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service

from elasticsearch import Elasticsearch, exceptions as es_exceptions

import db_util   # keyword 조회/DB 저장용
from sqls import SELECT_ALL_KEYWORDS, INSERT_ARTICLE

# ----- 로깅 설정 -----
LOG_FILENAME = 'log/crawler.log'

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
logger.propagate = False  # 중복 출력 방지

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
    # 프로세스 카운트 초기화
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

#chromedriver_autoinstaller.install()

def get_driver():
    options = Options()
    #options.binary_location = "/opt/chrome/chrome" # Headless 버전으로 교체     
    options.binary_location = "/opt/chrome/chrome-headless-shell"
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--lang=ko_KR')
    options.add_argument('--blink-settings=imagesEnabled=false')  # 이미지 로딩 차단
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-plugins')
    options.add_argument('--mute-audio')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    # options.add_argument('--single-process')  # 필요 시 테스트 권장
    options.add_argument('--remote-allow-origins=*')  # Chrome 111+ 보안 관련 이슈 대응
    options.add_argument('--window-size=1920,1080')

    base_path = os.path.dirname(__file__)
    driverLog_path = os.path.join(base_path, 'log', 'chromedriver.log')
    # ChromeDriver 서비스 생성 + 로그 경로 지정
    service = Service(
        executable_path='/usr/local/bin/chromedriver',
        service_args=[
            "--verbose",
            f"--log-path={driverLog_path}"
        ]
    )

    options.page_load_strategy = 'eager'  # 페이지 렌더링 대기 최적화
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
            "div.article-body",
            "div#article_body",
            "div.text",
            "article",
            "section",
            "main"
        ]

        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text

        # fallback: 전체 텍스트 (본문이 길 경우)
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
                    return selector  # 발견된 셀렉터 반환
            except Exception:
                continue
        time.sleep(0.5)
    raise TimeoutException("None of the selectors were found in time.")

def extract_news_content(url, driver=None):
    # 1) trafilatura 우선
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


    # 3) BeautifulSoup (직접 셀렉터 탐색)
    text = extract_with_bs4(url)
    if text:
        logger.info("[본문] requests+BeautifulSoup 추출 성공")
        return text

    # 4) selenium fallback
    if driver:
        try:
            selectors = [
                "div.article-body",
                "div#article_body",
                "div.text"
            ]

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

    connection_pool_error_count = 0  # ConnectionPool 관련 오류 카운터

    for i in range(retries):
        try:
            driver.get(url)
            time.sleep(wait_seconds)
            final_url = driver.current_url
            logger.info(f"[SELENIUM] 최종 원문 URL: {final_url}")
            return final_url
        except Exception as e:
            error_msg = str(e)
            # ConnectionPool 또는 ReadTimeout 관련 오류 감지
            #if 'ConnectionPool' in error_msg or 'Read timed out' in error_msg:
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
                    continue  # 드라이버 재생성 후 재시도

            elif isinstance(e, TimeoutException):
                logger.warning(f"[SELENIUM] Timeout 발생 ({i+1}/{retries}), url: {url} - {e}")
            elif isinstance(e, WebDriverException):
                logger.warning(f"[SELENIUM] WebDriver 예외: {e}, url: {url}")
            else:
                logger.warning(f"[SELENIUM] 기타 예외({i+1}/{retries}): {e}, url: {url}")
            # 기타 예외 발생 시도 다음 재시도로 넘어감

    # 모든 재시도 실패 후 한 번 더 드라이버 재시작 및 재시도 1회
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
        # 우리가 만든 통합 함수로 바로 호출
        content = extract_news_content(article_url, driver)
    except Exception as e:
        logger.warning(f"[collect_article_in_new_tab] 추출 실패: {e}")

    driver.close()
    driver.switch_to.window(original_handle)
    return content


def main():
    logger.info("=== [크롤러 시작] ===")
    config = get_config("config.ini")

    # 키워드 당 기사 수집 개수 제한
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
        cur.execute(SELECT_ALL_KEYWORDS)
        keywords = cur.fetchall()
        logger.info(f"[INFO] 키워드 조회: {len(keywords)}건")
    except Exception as e:
        logger.error(f"[DB] 키워드 조회 오류: {e}")
        cur.close()
        conn.close()
        return    

    logger.info(f"[INFO] 키워드 별 기사 수집 개수 제한: {articlecnf}건")

    driver = get_driver()  # 한 번만 생성하여 재사용
    try:
        for kid, kw in keywords:
            logger.info(f"\n[LOOP] 키워드: {kw} ({kid})")
            log_browser_and_tab_info(driver, logger)  
            url = f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(url)

            if not feed.entries:
                logger.warning(f"[WARNING] 피드 결과 없음: {kw}")
                continue

            for entry in feed['entries'][:articlecnf]:
#            for entry in feed['entries'][:20]:
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
                    "title": entry_title,
                    "url": article_url,
                    "published_at": pub_dt,
                    "content": content_clean,
                    "crawled_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                es_id = None
                try:
                    # Elasticsearch 인덱싱 (자동 ID 할당)
                    res = es.index(index="crawler_articles", document=doc)
                    es_id = res['_id']
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
                    conn.commit()  # 커밋 필수
                    logger.info("[DB] 저장 완료")
                except Exception as e:
                    logger.error(f"[DB] Insert error: {e}, URL: {article_url}")
                    # DB Insert 실패 시 ES 문서 삭제 시도
                    if es_id:
                        try:
                            es.delete(index="crawler_articles", id=es_id)
                            logger.info(f"[Elasticsearch] DB 저장 실패로 삭제한 문서 id: {es_id}")
                        except Exception as del_e:
                            logger.error(f"[Elasticsearch] 문서 삭제 실패: {del_e}")

            # 키워드 루프 내에서는 collect_zombies() 호출하지 않음

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

