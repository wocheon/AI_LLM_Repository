# Public Cloud 내 Claude Code 연동 설정 가이드

> 작성 기준일: 2026-07-08<br>
> 대상: AWS EC2 + Amazon Bedrock, GCP VM + Google Cloud Agent Platform(Vertex AI)<br>
> 목적: 클라우드 계정의 모델 플랫폼 과금/쿼터를 사용하여 Claude Code를 실행하는 표준 절차 정리

---

## 1. 핵심 요약

Public Cloud VM에서 Claude Code를 실행할 때는 **Claude Code CLI 자체는 VM 내부에서 실행**되지만, 모델 추론은 **Amazon Bedrock** 또는 **Google Cloud Agent Platform(Vertex AI)** 의 관리형 API로 호출된다.

따라서 다음을 명확히 구분해야 한다.

| 구분 | 의미 |
|---|---|
| 실행 위치 | Claude Code CLI, Git, 테스트 명령, 파일 편집은 VM 또는 로컬 개발 환경에서 실행 |
| 모델 호출 위치 | AWS Bedrock 또는 Google Cloud Agent Platform의 관리형 Claude 모델 API |
| 과금 주체 | Claude 구독이 아니라 AWS/GCP 계정의 Bedrock/Agent Platform 사용량 기반 과금 |
| 데이터 흐름 | 프롬프트, 필요한 코드/파일 컨텍스트, 도구 결과가 선택한 클라우드 모델 API로 전송됨 |
| 권한 기준 | AWS IAM 또는 GCP IAM/ADC(Application Default Credentials)에 의해 사용 가능 여부 결정 |

운영 환경에서는 **개인 Access Key 또는 장기 Service Account Key 사용을 피하고**, 가능하면 **Instance Profile, IAM Role, Workload Identity Federation, Service Account 연결 방식**을 우선 사용한다.

---

## 2. 전체 아키텍처

```text
[사용자]
   |
   | SSH / IDE Remote / Terminal
   v
[Cloud VM / 개발 VM]
   |
   | claude 명령 실행
   | repo 읽기, 파일 수정, 테스트 명령 실행
   v
[Claude Code CLI]
   |
   | HTTPS API 호출
   | 프롬프트 + 코드 컨텍스트 + 도구 실행 결과
   v
[AWS Bedrock or Google Cloud Agent Platform]
   |
   | Claude 모델 추론
   v
[응답 반환]
   |
   v
[VM 내 파일 수정 / 명령 실행 / PR 작업]
```

주의할 점은 **GCP VM에서 실행한다고 해서 모델 추론과 데이터 처리가 VM 내부에서만 끝나는 것은 아니라는 점**이다. Claude Code는 로컬/VM의 파일과 명령을 활용하지만, 모델 답변 생성을 위해 필요한 컨텍스트는 선택한 클라우드 제공자의 Claude 모델 API로 전송된다.

---

## 3. 공통 사전 준비

### 3.1 Claude Code 설치

Linux VM 기준 설치 예시는 다음과 같다.

```bash
# 설치 스크립트를 임시 파일로 받은 뒤 내용을 검토하고 실행
INSTALLER="$(mktemp)"
curl -fsSL https://claude.ai/install.sh -o "$INSTALLER"
less "$INSTALLER"
bash "$INSTALLER"
rm -f -- "$INSTALLER"

# 현재 사용자 PATH 확인
which claude || echo 'claude not found in PATH'

# 버전 확인
claude --version
```

설치 후 `~/.local/bin/claude`에 설치되었고 전역 실행이 필요하다면 아래처럼 처리할 수 있다.

```bash
# 전역 경로로 이동
sudo install -m 755 ~/.local/bin/claude /usr/local/bin/claude

# 확인
/usr/local/bin/claude --version
```

> 운영 VM에서 여러 사용자가 함께 사용하는 경우, 전역 설치보다 사용자별 설치가 더 안전할 수 있다. 전역 설치 시 버전 변경 영향 범위가 커진다.

### 3.2 프로젝트 디렉토리에서 실행

Claude Code는 일반적으로 현재 작업 디렉토리를 기준으로 프로젝트를 이해한다.

```bash
cd /path/to/your/repository

git status
claude
```

권장 실행 전 확인:

```bash
pwd
git remote -v
git status --short
```

---

# 4. AWS EC2 + Amazon Bedrock 연동

## 4.1 개요

AWS에서는 Amazon Bedrock을 통해 Anthropic Claude 모델을 호출할 수 있다. Claude Code는 Bedrock 인증 정보를 사용하여 모델을 호출하며, 사용량은 AWS 계정에 과금된다.

### 권장 인증 방식 우선순위

| 우선순위 | 방식 | 권장 여부 | 비고 |
|---:|---|---|---|
| 1 | EC2 Instance Profile / IAM Role | 권장 | 장기 Access Key 불필요 |
| 2 | AWS SSO Profile | 권장 | 사람 사용자에게 적합 |
| 3 | Bedrock API Key | 상황별 사용 | Bedrock 전용 인증이 필요할 때 |
| 4 | Access Key / Secret Key | 비권장 | 유출 위험. 단기 테스트 외 지양 |

---

## 4.2 Bedrock 모델 사용 설정

1. AWS Console에서 **Amazon Bedrock → Model catalog**로 이동한다.
2. Anthropic Claude 모델을 선택한다.
3. 최초 사용 시 use case form을 제출한다.
4. 모델 사용 가능 리전과 계정 권한을 확인한다.

AWS Organizations 환경에서는 관리 계정에서 최초 사용 설정을 처리하는 방식을 검토한다.

---

## 4.3 IAM 권한

운영 환경에서는 최소 권한 원칙을 적용한다. Claude Code가 Bedrock 모델을 호출하려면 일반적으로 다음 권한이 필요하다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowBedrockInvokeClaudeModels",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.*"
      ]
    },
    {
      "Sid": "AllowBedrockModelDiscovery",
      "Effect": "Allow",
      "Action": [
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    }
  ]
}
```

최초 모델 사용 설정 또는 Marketplace 구독 처리에는 별도 권한이 필요할 수 있다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "aws-marketplace:Subscribe",
        "aws-marketplace:Unsubscribe",
        "aws-marketplace:ViewSubscriptions"
      ],
      "Resource": "*"
    }
  ]
}
```

> 운영 계정에서는 `aws-marketplace:Subscribe` 권한을 모든 개발자에게 열어두기보다, 플랫폼/관리자 계정에서 1회 승인 후 일반 사용자는 `bedrock:InvokeModel*` 중심으로 제한하는 구성이 안전하다.

---

## 4.4 EC2 인증 설정

### 옵션 A. EC2 Instance Profile 사용 권장

EC2에 Bedrock 호출 권한이 있는 IAM Role을 연결한다.

확인:

```bash
aws sts get-caller-identity
aws configure list
```

### 옵션 B. AWS SSO Profile 사용

```bash
aws sso login --profile <YOUR_PROFILE>
export AWS_PROFILE=<YOUR_PROFILE>
aws sts get-caller-identity
```

### 옵션 C. Access Key 사용

장기 Access Key를 셸 명령이나 문서에 직접 입력하는 예시는 의도적으로 제공하지 않는다. 단기 테스트에서도 가능하면 AWS SSO 또는 임시 세션 자격증명을 사용하고, 불가피한 경우에는 조직의 Secret Manager와 자격증명 회전 정책을 따른다.

---

## 4.5 Claude Code 환경 변수

```bash
# Bedrock 통합 활성화
export CLAUDE_CODE_USE_BEDROCK=1

# AWS 리전. AWS Profile에 리전이 없거나 명시적으로 덮어쓸 때 사용
export AWS_REGION=us-east-1

# 선택: small/fast 모델을 다른 리전에서 사용할 때
# 단, Haiku 모델 또는 small/fast 모델 pinning을 사용할 때 의미가 있음
export ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION=us-west-2

# 선택: Bedrock Endpoint를 직접 지정해야 하는 특수 환경 또는 Gateway 사용 시
# export ANTHROPIC_BEDROCK_BASE_URL='https://bedrock-runtime.us-east-1.amazonaws.com'
```

영구 적용이 필요하면 shell profile에 추가한다.

```bash
cat <<'EOS' >> ~/.bashrc

# Claude Code - Amazon Bedrock
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=us-east-1
EOS

source ~/.bashrc
```

---

## 4.6 Claude Code Wizard 사용

수동 환경 변수 대신 Claude Code의 로그인 Wizard를 사용할 수 있다.

```bash
claude
```

선택 흐름:

```text
3rd-party platform
→ Amazon Bedrock
→ AWS profile / Bedrock API key / access key / credentials already in environment 중 선택
→ 리전 및 사용 모델 확인
→ 필요 시 모델 pinning
```

이미 설정한 뒤 변경하려면 Claude Code 내부에서 다음 명령을 실행한다.

```text
/setup-bedrock
```

---

## 4.7 Bedrock 연결 확인

```bash
# AWS 인증 확인
aws sts get-caller-identity

# Bedrock 모델 목록 확인
aws bedrock list-foundation-models --region "$AWS_REGION" \
  --query "modelSummaries[?contains(modelId, 'anthropic')].[modelId,providerName]" \
  --output table

# Claude Code 실행
claude
```

장애 발생 시 우선 확인할 항목:

```bash
echo "AWS_PROFILE=${AWS_PROFILE:-}"
echo "AWS_REGION=${AWS_REGION:-}"
aws configure list
aws sts get-caller-identity
```

---

# 5. GCP VM + Google Cloud Agent Platform(Vertex AI) 연동

## 5.1 개요

GCP에서는 Google Cloud Agent Platform, 기존 Vertex AI 경로를 통해 Anthropic Claude 모델을 호출할 수 있다. Claude Code 문서와 로그인 화면에는 여전히 `Vertex AI`라는 표현이 남아 있을 수 있지만, Google Cloud 문서에서는 Agent Platform 명칭을 함께 사용한다.

사용량은 GCP 프로젝트의 Agent Platform/Vertex AI 사용량으로 과금되며, 모델은 관리형 API 형태로 제공된다. 별도의 GPU VM이나 모델 서버를 직접 운영할 필요는 없다.

---

## 5.2 GCP 사전 준비

### 프로젝트 설정

```bash
export PROJECT_ID='YOUR-PROJECT-ID'

gcloud config set project "$PROJECT_ID"
gcloud config get-value project
```

### API 활성화

```bash
# 현재 활성화 여부 확인
gcloud services list --enabled --filter='config.name:aiplatform.googleapis.com'

# Agent Platform / Vertex AI API 활성화
gcloud services enable aiplatform.googleapis.com --project "$PROJECT_ID"
```

### Claude 모델 사용 설정

1. Google Cloud Console에서 **Model Garden**으로 이동한다.
2. `Claude`를 검색한다.
3. 사용할 Claude 모델 카드를 선택한다.
4. 필요한 사용 설정 또는 access request를 진행한다.
5. 사용할 리전 또는 global endpoint 지원 여부를 확인한다.

모델별로 사용 가능 리전과 endpoint 지원 여부가 다를 수 있으므로, 운영 반영 전 실제 프로젝트에서 호출 가능한 모델 ID를 확인해야 한다.

---

## 5.3 IAM 권한

일반적으로 `roles/aiplatform.user` 역할을 부여하면 Claude Code에서 필요한 Agent Platform 호출 권한을 포함한다.

### 사용자 계정에 부여

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member='user:your-email@example.com' \
  --role='roles/aiplatform.user'
```

### 서비스 계정에 부여

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member='serviceAccount:your-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com' \
  --role='roles/aiplatform.user'
```

보다 엄격하게 제한하려면 custom role을 사용해 `aiplatform.endpoints.predict` 중심으로 제한하는 방식을 검토한다.

---

## 5.4 GCP 인증 방식

### 권장 인증 방식 우선순위

| 우선순위 | 방식 | 권장 여부 | 비고 |
|---:|---|---|---|
| 1 | VM에 연결된 Service Account | 권장 | 운영 VM에 적합 |
| 2 | Workload Identity Federation | 권장 | 외부 IdP/CI 연동에 적합 |
| 3 | gcloud ADC 로그인 | 개발/테스트 적합 | 브라우저 인증 필요 |
| 4 | Service Account Key JSON | 비권장 | 키 유출 위험. 불가피할 때만 사용 |

### 옵션 A. VM Service Account 사용 권장

VM 생성 또는 수정 시 Agent Platform 호출 권한이 있는 Service Account를 연결한다.

확인:

```bash
gcloud auth list
gcloud config get-value project
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email
```

### 옵션 B. ADC(Application Default Credentials) 로그인

개발 VM에서 사용자 계정으로 테스트할 때 사용할 수 있다.

```bash
gcloud auth application-default login

gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'
```

브라우저 로그인이 필요한 환경이라면 SSH 터미널에 표시되는 URL을 브라우저에서 열어 인증한다.

### 옵션 C. Service Account Key JSON

보안상 권장하지 않지만, 불가피하게 사용할 경우 파일 권한과 보관 위치를 제한한다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS='/secure/path/service-account.json'
chmod 600 "$GOOGLE_APPLICATION_CREDENTIALS"
```

---

## 5.5 Claude Code 환경 변수

```bash
# Google Cloud Agent Platform / Vertex AI 통합 활성화
export CLAUDE_CODE_USE_VERTEX=1

# 리전 또는 endpoint 위치
# global, us, eu, us-east5 등 모델이 지원하는 위치 사용
export CLOUD_ML_REGION=global

# Agent Platform 요청에 사용할 GCP 프로젝트 ID
export ANTHROPIC_VERTEX_PROJECT_ID='YOUR-PROJECT-ID'

# 선택: prompt caching 비활성화가 필요한 경우에만 사용
# 기본적으로 prompt caching은 자동 활성화됨
# export DISABLE_PROMPT_CACHING=1

# 선택: 1시간 prompt cache TTL 요청. 비용이 더 높을 수 있음
# export ENABLE_PROMPT_CACHING_1H=1
```

영구 적용:

```bash
cat <<'EOS' >> ~/.bashrc

# Claude Code - Google Cloud Agent Platform / Vertex AI
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=global
export ANTHROPIC_VERTEX_PROJECT_ID='YOUR-PROJECT-ID'
EOS

source ~/.bashrc
```

---

## 5.6 모델 Pinning

운영 또는 팀 단위 배포에서는 모델 alias에 의존하지 말고 명시적으로 모델을 고정하는 것이 안전하다.

```bash
# 예시: 프로젝트에서 사용 가능한 모델 ID로 교체 필요
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-5'
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-8'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-haiku-4-5@20251001'
```

주의:

- `ANTHROPIC_MODEL='claude-opus-4-8@default'` 같은 단일 변수 방식은 의도한 provider model pinning과 다르게 동작할 수 있다.
- Claude Code의 `/model` 선택, `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL` 계열 변수는 우선순위와 용도가 다르다.
- Google Cloud Model Garden에서 실제 사용 가능한 모델 ID와 endpoint 위치를 확인한 뒤 적용한다.

---

## 5.7 Claude Code Wizard 사용

```bash
claude
```

선택 흐름:

```text
3rd-party platform
→ Google Vertex AI
→ Application Default Credentials / Service Account Key / credentials already in environment 중 선택
→ 프로젝트 및 리전 확인
→ 사용 가능한 Claude 모델 확인
→ 필요 시 모델 pinning
```

이미 설정한 뒤 변경하려면 Claude Code 내부에서 다음 명령을 실행한다.

```text
/setup-vertex
```

---

## 5.8 GCP 연결 확인

```bash
# 프로젝트 확인
gcloud config get-value project

# 인증 확인
gcloud auth list

gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'

# API 활성화 확인
gcloud services list --enabled --filter='config.name:aiplatform.googleapis.com'

# Claude Code 실행
claude
```

문제 발생 시 확인:

```bash
echo "CLAUDE_CODE_USE_VERTEX=${CLAUDE_CODE_USE_VERTEX:-}"
echo "CLOUD_ML_REGION=${CLOUD_ML_REGION:-}"
echo "ANTHROPIC_VERTEX_PROJECT_ID=${ANTHROPIC_VERTEX_PROJECT_ID:-}"
echo "GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS:-}"

gcloud config list
gcloud auth list
gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'
```

---

# 6. 비용, 쿼터, 데이터 처리 관점

## 6.1 비용

Cloud provider 연동 방식은 Claude Pro/Max 같은 개인 구독 한도를 사용하는 방식이 아니다.

| 항목 | AWS Bedrock | GCP Agent Platform |
|---|---|---|
| 과금 단위 | Bedrock 모델 토큰 사용량 | Agent Platform/Vertex AI 모델 토큰 사용량 |
| 청구 위치 | AWS Billing | GCP Cloud Billing |
| 무료 구독 필요 여부 | Claude 개인 구독 불필요 | Claude 개인 구독 불필요 |
| 한도 기준 | Bedrock quota, 리전별 모델 quota | Agent Platform quota, 프로젝트/리전별 quota |

## 6.2 쿼터

Claude Code 자체의 앱 구독 한도와 별개로, Bedrock/Agent Platform을 사용할 경우 클라우드 프로젝트 또는 계정의 quota가 적용된다.

운영 전 확인할 항목:

- 사용 모델별 TPM/RPM 또는 유사 quota
- 리전별 quota
- 조직 정책 또는 SCP/Organization Policy
- 예산 알림(Budget Alert)
- 모델별 단가
- prompt caching 사용 여부와 cache write 비용

## 6.3 데이터 처리

Claude Code는 코드베이스를 원격으로 전체 색인하는 방식이 아니라, 로컬/VM에서 파일을 읽고 필요한 컨텍스트를 모델 API로 전송하는 구조다. 따라서 다음 보안 정책이 필요하다.

- 민감정보가 포함된 파일은 `.gitignore`, `.claudeignore` 또는 접근 권한으로 보호
- `.env`, secret 파일, 인증서, private key를 작업 디렉토리에 방치하지 않기
- 운영 서버에서 직접 실행 시 read-only 권한 또는 테스트 전용 계정 사용
- destructive command 실행 전 diff/plan 확인
- Git branch 분리 후 작업
- PR 기반 리뷰 적용

---

# 7. 운영 권장 구성

## 7.1 개발/테스트 VM

```text
GCP/AWS Dev VM
→ repo clone
→ Claude Code 실행
→ branch 생성
→ 코드 수정
→ 테스트
→ commit 또는 PR 생성
```

권장:

```bash
git switch -c feature/claude-code-test
claude

git diff
git status
```

## 7.2 운영 서버 직접 실행 시 제한

운영 서버에서 Claude Code를 직접 실행할 수는 있지만 권장 기본값은 아니다. 불가피하게 사용한다면 다음 제한을 둔다.

- root 계정 실행 금지
- write 권한이 필요한 디렉토리 최소화
- systemctl, rm, chmod, chown, iptables, firewall-cmd 등 위험 명령은 수동 승인
- snapshot/backup 확인 후 작업
- 작업 전 `git status`, `git diff`, `systemctl status`, `df -h` 확인
- 변경 후 rollback 명령 준비

예시:

```bash
# 작업 전 확인
git status --short
git branch --show-current
df -h
systemctl --failed

# 변경 사항 확인
git diff --stat
git diff
```

---

# 8. Troubleshooting

## 8.1 AWS Bedrock

### AccessDeniedException

가능 원인:

- Bedrock 모델 사용 설정 미완료
- Anthropic first-time use form 미제출
- IAM Role에 `bedrock:InvokeModel` 권한 없음
- Marketplace 권한 부족
- 잘못된 리전 사용

확인:

```bash
aws sts get-caller-identity
aws configure list
aws bedrock list-foundation-models --region "$AWS_REGION" --output table
```

### 모델이 보이지 않음

가능 원인:

- 해당 리전에서 모델 미지원
- 계정의 모델 접근 권한 미완료
- Claude Code에서 다른 AWS_PROFILE 또는 AWS_REGION 사용

확인:

```bash
echo "$AWS_PROFILE"
echo "$AWS_REGION"
aws configure get region --profile "${AWS_PROFILE:-default}"
```

---

## 8.2 GCP Agent Platform / Vertex AI

### Permission denied 또는 403

가능 원인:

- `roles/aiplatform.user` 권한 없음
- 잘못된 ADC 계정 사용
- VM Service Account에 권한 없음
- 프로젝트 ID 불일치
- API 비활성화

확인:

```bash
gcloud config get-value project
gcloud auth list
gcloud services list --enabled --filter='config.name:aiplatform.googleapis.com'
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten='bindings[].members' \
  --filter='bindings.role:roles/aiplatform.user' \
  --format='table(bindings.role,bindings.members)'
```

### 모델 호출 실패

가능 원인:

- Model Garden에서 해당 Claude 모델 사용 설정 미완료
- 선택한 `CLOUD_ML_REGION`에서 모델 미지원
- pinning한 모델 ID가 프로젝트에서 사용 불가
- quota 부족

확인:

```bash
echo "$CLOUD_ML_REGION"
echo "$ANTHROPIC_VERTEX_PROJECT_ID"
claude --version
```

---

# 9. 기존 초안 대비 수정/보완 사항

| 항목 | 기존 초안 | 보완 내용 |
|---|---|---|
| 데이터 흐름 | 클라우드 내부 실행 중심 설명 | CLI 실행 위치와 모델 API 호출 위치를 분리해서 설명 |
| AWS 인증 | Access Key 생성 중심 | Instance Profile, AWS SSO 우선으로 변경 |
| GCP 인증 | ADC 로그인 중심 | VM Service Account, Workload Identity Federation 우선순위 추가 |
| GCP 명칭 | Vertex AI | Google Cloud Agent Platform / Vertex AI 병기 |
| 모델 지정 | `ANTHROPIC_MODEL='claude-opus-4-8@default'` | `ANTHROPIC_DEFAULT_*_MODEL` 기반 pinning 예시로 보완 |
| 권한 | `roles/aiplatform.user` 예시만 존재 | Bedrock invoke 권한, Marketplace 최초 설정 권한, GCP custom role 고려 추가 |
| 검증 절차 | 부족 | `aws sts`, `gcloud auth`, API 활성화, 모델 목록 확인 명령 추가 |
| 운영 안정성 | 부족 | 운영 서버 직접 실행 시 제한, rollback/diff 확인 절차 추가 |
| 비용/쿼터 | 간단 설명 | Claude 구독 한도와 cloud provider quota/과금 분리 설명 |

---

# 10. 권장 최종 사용 예시

## AWS Bedrock 빠른 실행 예시

```bash
cd /path/to/repo

aws sts get-caller-identity

export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=us-east-1

claude
```

## GCP Agent Platform 빠른 실행 예시

```bash
cd /path/to/repo

export PROJECT_ID='YOUR-PROJECT-ID'
gcloud config set project "$PROJECT_ID"
gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'

export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=global
export ANTHROPIC_VERTEX_PROJECT_ID="$PROJECT_ID"

claude
```

---

# 11. 참고 문서

- Claude Code on Amazon Bedrock: https://code.claude.com/docs/en/amazon-bedrock
- Claude Code on Google Cloud Agent Platform / Vertex AI: https://code.claude.com/docs/en/google-vertex-ai
- Claude Code Environment Variables: https://code.claude.com/docs/en/env-vars
- Amazon Bedrock model access: https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html
- Google Cloud Claude models on Agent Platform: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/claude
