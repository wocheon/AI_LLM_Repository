from flask import Flask, render_template, abort, request
import pymysql
import configparser
from collections import OrderedDict
from elasticsearch import Elasticsearch

app = Flask(__name__)

# --- Config 로드 ---
config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')

db_config = dict(config['database'])
es_config = dict(config['elasticsearch']) # ES 설정

# ES 클라이언트 연결
es_client = Elasticsearch(
    hosts=[{'host': es_config.get('host', 'elasticsearch'), 
            'port': int(es_config.get('port', 9200)), 
            'scheme': 'http'}]
)
SUMMARY_INDEX = es_config.get('summary_index', 'article_summary')

model_data_query = config.get('queries', 'model_data_query')
model_comparison_query = config.get('queries', 'model_comparison_query')
EMOJI_MAP = dict(config['emojis'])

def get_db_connection():
    return pymysql.connect(**db_config)

def get_available_models():
    """Config에서 정의된 모델 슬러그 목록 반환"""
    if config.has_section('models'):
        return list(config['models'].keys())
    return []

# -------------------------------------------------------------
# ES 요약문 조회 헬퍼 함수
# -------------------------------------------------------------
def fetch_summaries_from_es(article_ids):
    """article_id 리스트를 받아 {id: summary} 맵 반환"""
    summary_map = {}
    if not article_ids:
        return summary_map
        
    try:
        # DB ID(int) -> String 변환
        ids = [str(aid) for aid in article_ids]
        res = es_client.mget(index=SUMMARY_INDEX, body={"ids": ids})
        for doc in res['docs']:
            if doc['found']:
                summary_map[doc['_id']] = doc['_source'].get('summary', '')
    except Exception as e:
        print(f"ES Error: {e}")
    
    return summary_map

def get_data_by_model(model_slug):
    """단일 모델 결과 조회"""
    if not config.has_option('models', model_slug):
        return None
        
    db_model_name = config.get('models', model_slug)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(model_data_query, (db_model_name,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []

    # 1. ID 목록 추출 (3번째 컬럼인 content가 ES ID라고 하셨으므로)
    # 쿼리 순서: id(0), kw_id(1), title(2), content(3), url(4)...
    CONTENT_IDX = 4 
    es_ids = [row[CONTENT_IDX] for row in rows] # content 컬럼을 ID로 사용
    
    # 2. ES 요약 조회
    summary_map = fetch_summaries_from_es(es_ids)
    
    # 3. 데이터 병합 및 순서 재배치
    merged_rows = []

    for row in rows:
        row_list = list(row)
        es_id = str(row_list[CONTENT_IDX])
        
        # 요약 가져오기
        summary_text = summary_map.get(es_id, "요약 없음")
        
        # [핵심] url(4) 뒤에 summary(5) 추가
        # 현재 row_list: [id, kw, title, content, url, sent, score, pub, col]
        # insert(5, value) 하면 url(4) 뒤에 들어감
        row_list.insert(6, summary_text) 
        
        merged_rows.append(row_list)
        
    return merged_rows

def get_combined_model_data(model_slug_a, model_slug_b):
    """두 모델 비교 데이터 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    real_name_a = config.get('models', model_slug_a, fallback=model_slug_a)
    real_name_b = config.get('models', model_slug_b, fallback=model_slug_b)
    
    cursor.execute(model_comparison_query, (real_name_a, real_name_b))
    rows = cursor.fetchall()
    conn.close()

    combined_data = OrderedDict()
    
    for row in rows:
        article_id = row[0]

        if article_id not in combined_data:
            combined_data[article_id] = {
                'meta': {
                    'id': row[0], 
                    'keyword': row[1], 
                    'category': row[2], 
                    'title': row[3],
                    'content': row[4], 
                    'url': row[5], 
                    'published_at': row[6]
                },
                'models': {}
            }
        
        if row[7]: 
            combined_data[article_id]['models'][real_name_a] = {
                'sentiment': row[7], 'score': row[8]
            }
        if row[9]: 
            combined_data[article_id]['models'][real_name_b] = {
                'sentiment': row[9], 'score': row[10]
            }

    current_models = [real_name_a, real_name_b]
    full_emoji_map = {m: EMOJI_MAP for m in current_models}

    return combined_data, current_models, full_emoji_map


# --- 라우터 ---

@app.route('/')
def main():
    return render_template('main.html')

@app.route('/model/<model_name>')
def model_result(model_name):
    # 1. 데이터 조회 (기존 코드)
    data = get_data_by_model(model_name)
    if data is None:
        abort(404, description=f"Model '{model_name}' not found.")

    # 2. 감성 레이블 조회 (기존 코드)
    sentiments_str = config.get('sentiments', model_name, fallback='')
    sentiments = [s.strip() for s in sentiments_str.split(',') if s.strip()]

    # [추가] 3. 드롭다운을 만들기 위해 '전체 모델 목록' 가져오기
    # config.ini의 [models] 섹션을 딕셔너리로 가져옴
    # 예: {'kobert': 'KoBERT Model', 'electra': 'KoELECTRA Model', ...}
    try:
        all_models = dict(config.items('models')) 
    except Exception:
        # config에 models 섹션이 없거나 에러날 경우 대비
        all_models = {model_name: model_name}

    # 4. 템플릿 렌더링 (변수 추가)
    return render_template(
        'model_result.html',
        data=data,
        
        # 모델 이름 (화면 표시용)
        # config에 저장된 실명이 있으면 그걸 쓰고, 없으면 model_name 그대로 사용
        model_real_name=all_models.get(model_name, model_name), 
        
        # [핵심] 드롭다운 생성을 위한 데이터 전달
        all_models=all_models,       # 전체 모델 목록 ({'slug': 'Name', ...})
        current_slug=model_name,     # 현재 선택된 모델 (selected 처리용)
        
        sentiments=sentiments,
        emoji_map=EMOJI_MAP,
        active_tab=model_name # 이건 네비게이션용이라면 유지
    )

@app.route('/comparison')
def comparison():
    all_models = get_available_models()
    default_a = all_models[0] if all_models else 'kobert'
    default_b = all_models[1] if len(all_models) > 1 else default_a
    
    model1 = request.args.get('model1', default_a)
    model2 = request.args.get('model2', default_b)
    
    combined_data, current_models, emoji_map = get_combined_model_data(model1, model2)
    
    return render_template('comparison.html',
                           combined_data=combined_data,
                           model_list=current_models,
                           all_models=all_models,
                           selected_models={'a': model1, 'b': model2},
                           emoji_map=emoji_map,
                           active_tab='comparison')

# [NEW] 요약문 팝업 라우트
@app.route('/summary/<article_id>')
def view_summary(article_id):
    # 기본값 설정
    doc_data = {
        'title': '제목 없음',
        'keyword': 'N/A',
        'category': 'N/A',
        'content': '내용 없음',
        'crawled_at': 'N/A',
        'published_at': 'N/A',
        'summary': '요약 없음',
        'url': '#'
    }
    
    try:
        # ES에서 해당 ID의 문서 조회
        res = es_client.get(index=SUMMARY_INDEX, id=str(article_id))
        
        if res['found']:
            source = res['_source']
            doc_data = {
                'title': source.get('title', '제목 없음'),
                # keyword가 리스트일 경우 콤마로 연결
                'keyword': source.get('keyword', 'N/A'), 
                'category': source.get('category', 'N/A'),
                # 본문이 너무 길면 앞 300자만 자르기
                'content': source.get('content', '')[:300] + '...', 
                'crawled_at': source.get('crawled_at', 'N/A'),
                'published_at': source.get('published_at', 'N/A'),
                'summary': source.get('summary', '요약 데이터가 없습니다.'),
                'url': source.get('url', '#')
            }
            
            # 리스트 타입 처리 (키워드 등이 리스트로 저장된 경우)
            if isinstance(doc_data['keyword'], list):
                doc_data['keyword'] = ', '.join(doc_data['keyword'])
            if isinstance(doc_data['category'], list):
                doc_data['category'] = ', '.join(doc_data['category'])

    except es_exceptions.NotFoundError:
        doc_data['summary'] = f"문서(ID: {article_id})를 찾을 수 없습니다."
    except Exception as e:
        print(f"Error fetching summary: {e}")
        doc_data['summary'] = f"에러 발생: {e}"

    # 템플릿에 객체 통째로 전달
    return render_template('popup_summary.html', info=doc_data, article_id=article_id)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
