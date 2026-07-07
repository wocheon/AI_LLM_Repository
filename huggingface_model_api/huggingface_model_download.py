# huggingface_model_download.py
import os
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()
# 환경 변수에서 Hugging Face 토큰 불러오기 (.env 파일에 HF_TOKEN=your_token 형식으로 저장)
HF_TOKEN = os.getenv("HF_TOKEN")

api = HfApi(token=HF_TOKEN)

# 홈 디렉토리에 huggingface/models/fine_tunned_debert 경로 생성 및 모델 다운로드
local_dir = Path.home() / "huggingface/models/fine_tunned_debert"

api.snapshot_download(
    repo_id="wocheon/fine_tunned_debert",
    repo_type="model",
    local_dir=str(local_dir),
    local_dir_use_symlinks=False
)
