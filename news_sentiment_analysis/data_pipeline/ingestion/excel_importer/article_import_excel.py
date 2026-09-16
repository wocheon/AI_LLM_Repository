import pandas as pd
import pymysql
import configparser
import sys
import os
from datetime import datetime

# ==========================================
# 1. 설정 및 DB 연결
# ==========================================
def get_config(path="config.ini"):
    config = configparser.ConfigParser()
    config.read(path, encoding='utf-8')
    return config

def get_db_connection(config):
    db_cfg = config['database']
    return pymysql.connect(
        host=db_cfg['host'],
        user=db_cfg['user'],
        password=db_cfg['password'],
        db=db_cfg['dbname'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# ==========================================
# 2. 날짜 변환 함수
# ==========================================
def format_timestamp(ts):
    """
    엑셀의 20251231230051001 (int or str) -> '2025-12-31 23:00:51' (str)
    """
    ts_str = str(ts).strip()
    
    # 혹시 소수점(.0) 등이 붙어있으면 제거
    if '.' in ts_str:
        ts_str = ts_str.split('.')[0]
        
    # 길이가 짧으면 처리 불가
    if len(ts_str) < 14:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S') # 현재 시간으로 대체
        
    # 슬라이싱으로 포맷팅
    return f"{ts_str[:4]}-{ts_str[4:6]}-{ts_str[6:8]} {ts_str[8:10]}:{ts_str[10:12]}:{ts_str[12:14]}"

# ==========================================
# 3. 메인 로직
# ==========================================
def main():
    config = get_config("config.ini")
    
    # config에서 엑셀 파일 경로 읽기
    try:
        excel_cfg = config['excel']
        excel_file = excel_cfg['dataset_file']
    except KeyError:
        print("[오류] config.ini에 [excel] 섹션이나 dataset_file 키가 없습니다.")
        return

    # 파일 존재 확인
    if not os.path.exists(excel_file):
        print(f"[오류] 파일이 존재하지 않습니다: {excel_file}")
        return

    print(f"1. 엑셀 파일 읽는 중... ({excel_file})")
    try:
        df = pd.read_excel(excel_file)
        # 만약 첫 번째 행이 헤더가 아니라면 header=None 옵션 확인 필요
    except Exception as e:
        print(f"엑셀 읽기 실패: {e}")
        return

    print(f"   -> 총 {len(df)}개 행 발견")
    
    # 데이터 전처리 (리스트 변환)
    data_to_insert = []
    
    for _, row in df.iterrows():
        section = str(row['section']).strip()
        title = str(row['title']).strip()
        url = str(row['url']).strip()
        raw_pub = row['published_at']
        
        # 날짜 변환
        published_at = format_timestamp(raw_pub)
        
        # 튜플로 저장 (순서: section, title, url, published_at, crawled_at)
        # crawled_at은 현재 시간
        crawled_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        data_to_insert.append((section, title, url, published_at, crawled_at))

    print("2. DB 저장 시작...")
    config = get_config("config.ini")
    conn = get_db_connection(config)
    
    try:
        with conn.cursor() as cur:
            # INSERT IGNORE: 중복 키(URL)가 있으면 에러 대신 경고를 내고 무시함 (Skip)
            sql = """
                INSERT IGNORE INTO article_dataset
                (section, title, url, published_at, crawled_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            # executemany로 한 번에 처리 (속도 매우 빠름)
            affected_rows = cur.executemany(sql, data_to_insert)
            conn.commit()
            
            print(f"   -> 완료! {affected_rows}건이 새로 저장되었습니다.")
            print(f"   -> (전체 {len(data_to_insert)}건 중 중복 제외됨)")
            
    except Exception as e:
        print(f"DB 저장 중 오류 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()

