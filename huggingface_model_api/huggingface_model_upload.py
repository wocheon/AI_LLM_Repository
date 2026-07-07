# huggingface_model_upload.py
# 토큰을 통해 HuggingFace 로그인 확인
import os
from dotenv import load_dotenv
from huggingface_hub
import HfApi

# 환경 변수에서 Hugging Face 토큰 불러오기 (.env 파일에 HF_TOKEN=your_token 형식으로 저장)
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

# 2. 이제 login() 호출 없이도 바로 사용 가능
from huggingface_hub import HfApi

api = HfApi()
user_info = api.whoami()
print(f"로그인된 사용자: {user_info['name']}")


local_dir = os.path.expanduser(
    "~/huggingface/models/fine_tunned_koelectra"
)

# 파일업로드
api.upload_folder(folder_path=str(local_dir) ,
                repo_id="wocheon/fine_tunned_koelectra",
                repo_type="model")
