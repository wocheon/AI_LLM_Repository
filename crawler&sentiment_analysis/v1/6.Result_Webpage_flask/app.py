from flask import Flask, render_template, abort, request
import pymysql
import configparser
from collections import OrderedDict

app = Flask(__name__)

# --- Config 로드 ---
# interpolation=None: % 문자 에러 방지
config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')

db_config = dict(config['database'])
model_data_query = config.get('queries', 'model_data_query')
model_comparison_query = config.get('queries', 'model_comparison_query')

# 공통 이모지 맵 로드
EMOJI_MAP = dict(config['emojis'])

def get_db_connection():
    return pymysql.connect(**db_config)

def get_available_models():
    """Config에서 정의된 모델 슬러그 목록 반환"""
    if config.has_section('models'):
        return list(config['models'].keys())
    return []

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
    return rows

def get_combined_model_data(model_slug_a, model_slug_b):
    """두 모델 비교 데이터 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # URL 슬러그 -> DB 실제 모델명 변환
    real_name_a = config.get('models', model_slug_a, fallback=model_slug_a)
    real_name_b = config.get('models', model_slug_b, fallback=model_slug_b)
    
    # 쿼리 실행 (파라미터 2개 전달)
    cursor.execute(model_comparison_query, (real_name_a, real_name_b))
    rows = cursor.fetchall()
    conn.close()

    combined_data = OrderedDict()
    
    # 쿼리 컬럼 순서 (config.ini 쿼리에 맞춰 조정 필수)
    # 예: 0:id, 1:kw_id, 2:title, 3:cont, 4:url, 5:pub, 6:r1_sent, 7:r1_score, 8:r2_sent, 9:r2_score
    for row in rows:
        article_id = row[0]
        
        if article_id not in combined_data:
            combined_data[article_id] = {
                'meta': {
                    'id': row[0], 
                    'keyword_id': row[1], 
                    'title': row[2],
                    'content': row[3], # preview
                    'url': row[4],     # url
                    'published_at': row[5] # pub date
                },
                'models': {}
            }
        
        # Model A 결과 (r1)
        if row[6]: 
            combined_data[article_id]['models'][real_name_a] = {
                'sentiment': row[6], 
                'score': row[7]
            }
            
        # Model B 결과 (r2)
        if row[8]: 
            combined_data[article_id]['models'][real_name_b] = {
                'sentiment': row[8], 
                'score': row[9]
            }

    # 현재 비교 중인 실제 모델명 리스트
    current_models = [real_name_a, real_name_b]
    
    # 이모지 맵 생성
    full_emoji_map = {m: EMOJI_MAP for m in current_models}

    return combined_data, current_models, full_emoji_map


# --- 라우터 ---

@app.route('/')
def main():
    return render_template('main.html')

@app.route('/model/<model_name>')
def model_result(model_name):
    data = get_data_by_model(model_name)
    if data is None:
        abort(404, description=f"Model '{model_name}' not found in config.")

    sentiments_str = config.get('sentiments', model_name, fallback='')
    sentiments = [s.strip() for s in sentiments_str.split(',') if s.strip()]

    return render_template(
        'model_result.html',
        data=data,
        model_name=model_name,
        sentiments=sentiments,
        emoji_map=EMOJI_MAP,
        active_tab=model_name
    )

@app.route('/comparison')
def comparison():
    # 1. 전체 모델 목록 (드롭다운용)
    all_models = get_available_models()
    
    # 2. 파라미터 파싱 (기본값: 목록의 첫번째, 두번째 모델)
    default_a = all_models[0] if all_models else 'kobert'
    default_b = all_models[1] if len(all_models) > 1 else default_a
    
    model1 = request.args.get('model1', default_a)
    model2 = request.args.get('model2', default_b)
    
    # 3. 데이터 조회
    combined_data, current_models, emoji_map = get_combined_model_data(model1, model2)
    
    return render_template('comparison.html',
                           combined_data=combined_data,
                           model_list=current_models, # [실제이름A, 실제이름B]
                           all_models=all_models,     # [슬러그1, 슬러그2...]
                           selected_models={'a': model1, 'b': model2},
                           emoji_map=emoji_map,
                           active_tab='comparison')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

