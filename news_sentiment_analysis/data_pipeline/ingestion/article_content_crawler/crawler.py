import configparser
import urllib.parse
import time
import os
import psutil
import logging
import sys
import random
import requests

# [핵심] Anti-Bot 라이브러리
import undetected_chromedriver as uc
from curl_cffi import requests as cffi_requests
from fake_useragent import UserAgent

# [핵심] 파싱 라이브러리
from bs4 import BeautifulSoup
from newspaper import Article
import trafilatura

# [핵심] Selenium 관련
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# [핵심] ES
from elasticsearch import Elasticsearch

# 모듈 로거 생성 (핸들러 설정 없음 -> 호출하는 쪽 설정을 따름)
logger = logging.getLogger(__name__)

# ----- 1. 시스템/설정 유틸리티 -----

def get_config(path="config.ini"):
    config = configparser.ConfigParser()
    config.read(path)
    return config

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
    return es

def collect_zombies():
    """좀비 프로세스 정리"""
    try:
        while True:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
    except (ChildProcessError, OSError):
        pass

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

def log_browser_and_tab_info(driver, custom_logger=None):
    log = custom_logger if custom_logger else logger

    # 프로세스 카운트
    chrome_cnt = 0
    driver_cnt = 0
    try:
        for proc in psutil.process_iter(['name']):
            name = (proc.info['name'] or "").lower()
            if 'chrome' in name and 'chromedriver' not in name:
                chrome_cnt += 1
            elif 'chromedriver' in name:
                driver_cnt += 1
        log.info(f"[Resource] Chrome: {chrome_cnt}, Driver: {driver_cnt}")
    except:
        pass

    # 탭 카운트
    if driver:
        try:
            log.info(f"[Selenium] Open Tabs: {len(driver.window_handles)}")
        except:
            pass


# ----- 2. 브라우저/네트워크 코어 (Anti-Bot 적용) -----

def get_driver():
    """Undetected ChromeDriver 반환 (ChromeOptions 재사용 금지)"""
    # 1. 매 호출마다 새 객체 생성
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--lang=ko_KR')
    options.add_argument('--disable-popup-blocking')

    # 윈도우 사이즈 및 UA 랜덤화
    sizes = ["1920,1080", "1366,768", "1536,864", "1440,900"]
    options.add_argument(f'--window-size={random.choice(sizes)}')
    try:
        options.add_argument(f'--user-agent={UserAgent().random}')
    except:
        pass

    # Docker 환경에 수동 설치된 chromedriver 경로 사용
    try:
        driver = uc.Chrome(
            options=options,
            use_subprocess=True,
            driver_executable_path='/usr/local/bin/chromedriver',
            version_main=None, # 수동 설치 시 버전 체크 생략 권장
            log_level=0
        )
    except TypeError:
        # 구버전 호환성
        driver = uc.Chrome(
            options=options,
            use_subprocess=True,
            driver_executable_path='/usr/local/bin/chromedriver'
        )

    driver.set_page_load_timeout(30)
    return driver

def fetch_html_stealth(url):
    """curl_cffi를 사용한 TLS Fingerprint 우회 요청"""
    try:
        # logger.debug(f"Stealth Fetching: {url}")
        resp = cffi_requests.get(
            url,
            impersonate="chrome120",
            timeout=20,
            headers={'Referer': 'https://www.google.com/'}
        )
        if resp.status_code == 200:
            return resp.text
        else:
            logger.warning(f"[Stealth Fetch] Status {resp.status_code} : {url}")
    except Exception as e:
        logger.warning(f"[Stealth Fetch] Failed: {e}")
    return None


# ----- 3. 추출/파싱 로직 -----

def simulate_human_behavior(driver):
    """스크롤 등을 통한 기계적 패턴 파괴"""
    try:
        driver.execute_script(f"window.scrollTo(0, {random.randint(200, 600)});")
        time.sleep(random.uniform(0.3, 0.8))
    except:
        pass

def extract_with_bs4(html):
    if not html: return None
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # 주요 본문 영역 우선 탐색
        for sel in ["div.article-body", "div#article_body", "div.text", "section", "article"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(separator=" ", strip=True)
                if len(txt) > 100: return txt
        # 전체 텍스트 fallback
        txt = soup.get_text(separator=" ", strip=True)
        return txt if len(txt) > 100 else None
    except:
        return None

def extract_news_content(url, driver=None):
    """
    본문 추출 통합 함수
    1. Stealth Request -> Trafilatura
    2. Stealth Request -> Newspaper3k
    3. Selenium (Undetected) -> CSS Selectors
    """
    # 1. 정적 수집 시도 (브라우저 없이 빠르고 안전하게)
    html = fetch_html_stealth(url)

    if html:
        # Trafilatura
        try:
            content = trafilatura.extract(html)
            if content and len(content) > 100:
                logger.info("[본문] Trafilatura + Cffi 추출 성공")
                return content
        except: pass

        # Newspaper3k
        try:
            a = Article(url, language='ko')
            a.download(input_html=html)
            a.parse()
            if a.text and len(a.text) > 100:
                logger.info("[본문] Newspaper3k + Cffi 추출 성공")
                return a.text
        except: pass

        # BS4
        bs_text = extract_with_bs4(html)
        if bs_text:
            logger.info("[본문] BS4 + Cffi 추출 성공")
            return bs_text

    # 2. 동적 수집 (Selenium) - 최후의 수단
    if driver:
        try:
            logger.info("[본문] Selenium Fallback 시도 (Undetected)")
            driver.get(url)
            time.sleep(random.uniform(2.0, 4.0)) # 로딩 대기
            simulate_human_behavior(driver)

            # CSS Selector Loop
            selectors = ["div.article-body", "div#article_body", "div.text", "article", "section", "main"]
            for sel in selectors:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    txt = els[0].text.strip()
                    if len(txt) > 50:
                        logger.info(f"[본문] Selenium ({sel}) 추출 성공")
                        return txt

            # Tag Fallback
            for tag in ["article", "main"]:
                els = driver.find_elements(By.TAG_NAME, tag)
                if els:
                    txt = els[0].text.strip()
                    if len(txt) > 50:
                        logger.info(f"[본문] Selenium <{tag}> 추출 성공")
                        return txt

        except Exception as e:
            logger.warning(f"[Selenium Extract] Error: {e}")

    logger.info("[본문] 모든 방법 실패")
    return None

def collect_article_in_new_tab(article_url, driver):
    """새 탭을 열어 수집하거나, 정적 수집이 가능하면 바로 수집"""
    # 정적 수집 우선 시도 (탭 열기 오버헤드 및 탐지 방지)
    content = extract_news_content(article_url, driver=None)
    if content: return content

    # 실패 시 Selenium 탭 사용
    logger.info(" > 정적 수집 실패, 브라우저 탭 오픈 시도...")
    main_window = driver.current_window_handle
    try:
        driver.execute_script(f"window.open('{article_url}');")
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(len(driver.window_handles)))
        driver.switch_to.window(driver.window_handles[-1])

        content = extract_news_content(article_url, driver=driver)
    except Exception as e:
        logger.warning(f"[Tab Error] {e}")
        content = None
    finally:
        # 탭 정리
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(main_window)
        except: pass

    return content

def resolve_final_url_with_selenium(url, driver=None, retries=2):
    """리다이렉트 추적 (Google News 등)"""
    should_quit = False
    if not driver:
        driver = get_driver()
        should_quit = True

    final_url = url
    try:
        for i in range(retries):
            try:
                driver.get(url)
                time.sleep(random.uniform(2.0, 4.0)) # 리다이렉트 대기

                current = driver.current_url
                # 구글 뉴스 페이지가 아닌, 리다이렉트된 실제 뉴스 사이트인지 확인
                if "news.google.com" not in current and current != url:
                    final_url = current
                    logger.info(f"[Redirect] {url} -> {final_url}")
                    break
            except Exception as e:
                logger.warning(f"[Resolve Retry {i+1}] {e}")
                time.sleep(2)
    finally:
        if should_quit:
            try: driver.quit()
            except: pass

    return final_url