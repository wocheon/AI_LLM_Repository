# GCP VM 내 Antigravity CLI + Vertex AI Gemini 연동 설정 가이드

> 작성 기준일: 2026-07-08<br>
> 대상: GCP Compute Engine VM + Antigravity CLI + Google Cloud Agent Platform(Vertex AI) Gemini<br>
> 목적: GCP 프로젝트의 Agent Platform/Vertex AI 과금·쿼터를 사용하여 Antigravity CLI에서 Gemini 모델을 실행하는 표준 절차 정리

---

## 1. 핵심 요약

GCP VM에서 Antigravity CLI를 실행할 때는 **Antigravity CLI 자체는 VM 내부에서 실행**되지만, 모델 추론은 **Google Cloud Agent Platform(Vertex AI)의 Gemini 관리형 API**로 호출된다.

따라서 다음을 명확히 구분해야 한다.

| 구분 | 의미 |
|---|---|
| 실행 위치 | `agy` CLI, Git, 테스트 명령, 파일 편집은 GCP VM 또는 로컬 개발 환경에서 실행 |
| 모델 호출 위치 | Google Cloud Agent Platform(Vertex AI)의 관리형 Gemini 모델 API |
| 과금 주체 | 개인 Google AI Pro/Ultra 구독이 아니라 GCP 프로젝트의 Agent Platform/Vertex AI 사용량 기반 과금 |
| 데이터 흐름 | 프롬프트, 필요한 코드/파일 컨텍스트, 도구 실행 결과가 선택한 Google Cloud 모델 API로 전송됨 |
| 권한 기준 | Google Cloud IAM, Billing, Agent Platform API, ADC(Application Default Credentials) 또는 VM Service Account 상태에 의해 사용 가능 여부 결정 |

운영 환경에서는 **개인 계정 브라우저 로그인이나 장기 Service Account Key JSON 사용을 피하고**, 가능하면 **VM에 연결된 Service Account** 또는 **Service Account Impersonation** 방식을 우선 사용한다.

---

## 2. 전체 아키텍처

```text
[사용자]
   |
   | SSH / Remote Terminal / IDE Remote
   v
[GCP Compute Engine VM / 개발 VM]
   |
   | agy 명령 실행
   | repo 읽기, 파일 수정, 테스트 명령 실행
   v
[Antigravity CLI]
   |
   | HTTPS API 호출
   | 프롬프트 + 코드 컨텍스트 + 도구 실행 결과
   v
[Google Cloud Agent Platform / Vertex AI]
   |
   | Gemini 모델 추론
   v
[응답 반환]
   |
   v
[VM 내 파일 수정 / 명령 실행 / PR 작업]
```

주의할 점은 **GCP VM에서 실행한다고 해서 모델 추론과 데이터 처리가 VM 내부에서만 끝나는 것은 아니라는 점**이다. Antigravity CLI는 VM의 파일과 명령을 활용하지만, 모델 답변 생성을 위해 필요한 컨텍스트는 Google Cloud Agent Platform(Vertex AI)의 Gemini API로 전송된다.

---

## 3. 사전 준비

### 3.1 GCP 프로젝트 준비

다음 항목이 준비되어 있어야 한다.

| 항목 | 필요 여부 | 설명 |
|---|---:|---|
| GCP Project | 필수 | Antigravity CLI가 사용할 과금·쿼터 단위 |
| Billing | 필수 | Agent Platform/Vertex AI 사용량 과금 필요 |
| Agent Platform API | 필수 | `aiplatform.googleapis.com` 활성화 필요 |
| IAM 권한 | 필수 | 사용자 또는 VM Service Account에 `roles/aiplatform.user` 권한 필요 |
| Gemini 모델 사용 가능 상태 | 필수 | 프로젝트/리전에서 Gemini 모델 호출 가능해야 함 |
| gcloud CLI | 권장 | 인증, 프로젝트 설정, API 활성화 확인에 사용 |

---

### 3.2 프로젝트 ID 설정

```bash
export PROJECT_ID='YOUR-PROJECT-ID'

gcloud config set project "$PROJECT_ID"
gcloud config get-value project
```

현재 VM이 어떤 프로젝트에 속해 있는지 확인하려면 다음 명령을 사용할 수 있다.

```bash
curl -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id
```

---

### 3.3 Agent Platform API 활성화

```bash
# 현재 활성화 여부 확인
gcloud services list --enabled \
  --filter='config.name:aiplatform.googleapis.com' \
  --project "$PROJECT_ID"

# Agent Platform / Vertex AI API 활성화
gcloud services enable aiplatform.googleapis.com \
  --project "$PROJECT_ID"
```

API 활성화 권한이 없다면 관리자에게 `roles/serviceusage.serviceUsageAdmin` 또는 이에 준하는 custom role 부여를 요청한다.

---

## 4. IAM 권한 설정

## 4.1 기본 권한

Antigravity CLI가 GCP 프로젝트의 Gemini 모델을 호출하려면 일반적으로 사용자 계정 또는 VM Service Account에 다음 역할이 필요하다.

| 역할 | Role ID | 용도 |
|---|---|---|
| Agent Platform User | `roles/aiplatform.user` | Agent Platform/Vertex AI 모델 호출 |
| Service Usage Viewer | `roles/serviceusage.serviceUsageViewer` | API 활성화 상태 확인 시 필요할 수 있음 |
| Service Usage Admin | `roles/serviceusage.serviceUsageAdmin` | API 활성화 작업을 직접 수행할 때 필요 |

모델 호출만 수행하는 사용자 또는 서비스 계정에는 우선 `roles/aiplatform.user`를 부여하고, API 활성화·IAM 변경 권한은 운영자/관리자 계정에만 제한하는 구성이 안전하다.

---

## 4.2 사용자 계정에 권한 부여

개발자가 직접 브라우저 기반 Google Cloud 인증을 사용할 경우 사용자 계정에 권한을 부여한다.

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member='user:your-email@example.com' \
  --role='roles/aiplatform.user'
```

그룹 단위로 관리하는 경우 다음과 같이 부여할 수 있다.

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member='group:dev-team@example.com' \
  --role='roles/aiplatform.user'
```

---

## 4.3 VM Service Account에 권한 부여 권장

운영 또는 공용 개발 VM에서는 사용자 개인 인증보다 VM에 연결된 Service Account를 사용하는 방식이 더 관리하기 쉽다.

```bash
export SA_NAME='antigravity-cli-sa'
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 서비스 계정 생성
gcloud iam service-accounts create "$SA_NAME" \
  --display-name='Antigravity CLI Service Account' \
  --project "$PROJECT_ID"

# Agent Platform 호출 권한 부여
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role='roles/aiplatform.user'
```

VM에 연결된 Service Account 확인:

```bash
curl -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email
```

VM Service Account를 변경해야 하는 경우에는 작업 영향 범위를 먼저 확인한다.

```bash
export VM_NAME='YOUR-VM-NAME'
export ZONE='asia-northeast3-a'

# 현재 VM Service Account 확인
gcloud compute instances describe "$VM_NAME" \
  --zone "$ZONE" \
  --format='get(serviceAccounts.email)'

# 변경 전 VM 정지 필요 여부와 운영 영향 확인 후 수행
# 주의: VM Service Account 변경은 해당 VM에서 실행되는 다른 워크로드 권한에도 영향을 줄 수 있음
gcloud compute instances set-service-account "$VM_NAME" \
  --zone "$ZONE" \
  --service-account "$SA_EMAIL" \
  --scopes='https://www.googleapis.com/auth/cloud-platform'
```

> 운영 VM에서 Service Account를 변경하면 기존 배치, 모니터링 에이전트, 배포 스크립트의 권한 동작이 달라질 수 있다. 변경 전 `gcloud compute instances describe` 결과와 기존 워크로드 의존성을 반드시 확인한다.

---

## 5. 인증 방식

### 5.1 권장 인증 방식 우선순위

| 우선순위 | 방식 | 권장 여부 | 비고 |
|---:|---|---|---|
| 1 | VM에 연결된 Service Account | 권장 | 운영/공용 개발 VM에 적합. 장기 키 불필요 |
| 2 | Service Account Impersonation | 권장 | 사용자 인증은 유지하되 실제 호출 권한은 서비스 계정으로 통제 |
| 3 | ADC 사용자 로그인 | 개발/테스트 적합 | 브라우저 인증 필요. 개인 계정 의존성 존재 |
| 4 | Service Account Key JSON | 비권장 | 장기 키 유출 위험. 불가피할 때만 제한적으로 사용 |
| 5 | API Key | 상황별 사용 | 간단하지만 권한 경계와 키 유출 관리가 어려움 |

---

### 5.2 옵션 A. VM Service Account 사용 권장

GCP VM에서 실행되는 워크로드는 기본적으로 Metadata Server를 통해 VM에 연결된 Service Account 인증 정보를 사용할 수 있다.

확인:

```bash
# VM에 연결된 서비스 계정 확인
curl -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email

# 현재 gcloud 계정 확인
gcloud auth list

# 현재 프로젝트 확인
gcloud config get-value project
```

Antigravity CLI의 Google Cloud project 로그인 또는 credentials already in environment 옵션에서 이 인증을 사용할 수 있다.

---

### 5.3 옵션 B. ADC(Application Default Credentials) 사용자 로그인

개발/테스트 VM에서 개인 사용자 계정으로 테스트할 때 사용할 수 있다.

```bash
gcloud auth login

gcloud auth application-default login

gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'
```

SSH 환경에서는 브라우저가 자동으로 열리지 않을 수 있다. 이 경우 터미널에 출력되는 인증 URL을 로컬 브라우저에서 열어 인증을 완료한다.

---

### 5.4 옵션 C. Service Account Impersonation

사용자는 본인 계정으로 로그인하지만, 실제 모델 호출은 지정된 Service Account 권한으로 수행하게 만들 수 있다.

사전 조건:

```bash
# 사용자에게 Service Account Token Creator 권한 부여 필요
export USER_EMAIL='your-email@example.com'

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="user:${USER_EMAIL}" \
  --role='roles/iam.serviceAccountTokenCreator' \
  --project "$PROJECT_ID"
```

ADC에 Impersonation 적용:

```bash
gcloud auth application-default login \
  --impersonate-service-account="$SA_EMAIL"

gcloud auth application-default print-access-token >/dev/null && echo 'ADC impersonation OK'
```

이 방식은 사용자별 추적성과 서비스 계정 기반 권한 통제를 함께 가져갈 수 있어, 팀 단위 개발 환경에 적합하다.

---

### 5.5 옵션 D. Service Account Key JSON 비권장

보안상 권장하지 않는다. 불가피하게 사용할 경우 파일 권한과 저장 위치를 제한한다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS='/secure/path/antigravity-cli-sa.json'
chmod 600 "$GOOGLE_APPLICATION_CREDENTIALS"

gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'
```

키 파일은 다음 원칙을 적용한다.

- Git repository 안에 저장 금지
- VM 공용 디렉토리에 저장 금지
- 사용 후 즉시 폐기 또는 rotation
- Secret Manager, OS Login, IAM 조건부 접근 등과 함께 관리

---

## 6. Antigravity CLI 설치

## 6.1 Linux VM 설치

Linux/macOS에서는 공식 설치 스크립트를 사용할 수 있다.

```bash
# 필수 패키지 확인
sudo apt-get update
sudo apt-get install -y curl ca-certificates

# 설치 스크립트를 임시 파일로 받은 뒤 내용을 검토하고 실행
INSTALLER="$(mktemp)"
curl -fsSL https://antigravity.google/cli/install.sh -o "$INSTALLER"
less "$INSTALLER"
bash "$INSTALLER"
rm -f -- "$INSTALLER"
```

설치 후 `agy` 명령이 `PATH`에 잡히는지 확인한다.

```bash
export PATH="$HOME/.local/bin:$PATH"

command -v agy
agy --version
```

영구 적용이 필요하면 다음을 추가한다.

```bash
grep -q 'export PATH="$HOME/.local/bin:$PATH"' ~/.bashrc || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

source ~/.bashrc
```

---

## 6.2 전역 설치 여부

Antigravity CLI는 기본적으로 사용자 홈 디렉토리의 `~/.local/bin` 아래에 설치되는 방식이 일반적이다. 운영 VM에서 여러 사용자가 함께 사용할 경우 전역 설치보다 **사용자별 설치**를 권장한다.

전역 배치가 꼭 필요한 경우에는 버전 변경 영향 범위를 고려한 뒤 수행한다.

```bash
# 현재 agy 위치 확인
command -v agy

# 전역 경로로 복사해야 하는 경우
sudo install -m 755 "$(command -v agy)" /usr/local/bin/agy

# 확인
/usr/local/bin/agy --version
```

> 전역 설치 시 한 사용자의 업데이트가 다른 사용자의 작업에도 영향을 줄 수 있다. 팀 공용 VM에서는 사용자별 설치 또는 별도 dev VM 분리를 권장한다.

---

## 7. GCP 프로젝트 연동

## 7.1 Antigravity CLI 실행

작업할 repository 디렉토리로 이동한 뒤 실행한다.

```bash
cd /path/to/your/repository

pwd
git remote -v
git status --short

agy
```

---

## 7.2 로그인/프로젝트 선택 흐름

Antigravity CLI 최초 실행 시 다음 중 하나의 흐름을 선택할 수 있다.

```text
Antigravity CLI 실행
→ Google 로그인 또는 Google Cloud project 사용 선택
→ Use Google Cloud project 선택
→ 브라우저 또는 터미널 URL 기반 인증
→ 사용할 GCP Project 선택
→ Agent Platform/Vertex AI 기반 Gemini 모델 사용
```

일반적으로 다음과 같이 구분한다.

| 선택지 | 의미 | 과금/쿼터 |
|---|---|---|
| Google OAuth / 개인 Google 로그인 | 개인 계정 또는 Antigravity 개인 플랜 기반 사용 | 개인 계정/플랜 정책 적용 |
| Google Cloud project | GCP 프로젝트의 Agent Platform/Vertex AI 기반 사용 | GCP Cloud Billing 및 프로젝트 quota 적용 |

GCP VM에서 `Google Cloud project`를 선택하더라도, 모델 호출을 위해 프롬프트와 필요한 코드 컨텍스트는 Google Cloud Agent Platform API로 전송된다. 즉, **VM 안에서만 모델이 실행되는 구조는 아니다.**

---

## 7.3 프로젝트 연동 전 확인 명령

Antigravity CLI 실행 전에 다음을 확인한다.

```bash
export PROJECT_ID='YOUR-PROJECT-ID'

gcloud config set project "$PROJECT_ID"

# 프로젝트 확인
gcloud config get-value project

# Billing 연결 여부는 콘솔 또는 billing API 권한이 있는 계정으로 확인
# 권한이 있다면 다음 명령 사용 가능
gcloud beta billing projects describe "$PROJECT_ID"

# Agent Platform API 활성화 확인
gcloud services list --enabled \
  --filter='config.name:aiplatform.googleapis.com' \
  --project "$PROJECT_ID"

# 현재 인증 확인
gcloud auth list

# ADC 확인
gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'

# VM Service Account 확인
curl -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email
```

---

## 7.4 권장 실행 예시

```bash
cd /path/to/your/repository

export PROJECT_ID='YOUR-PROJECT-ID'
gcloud config set project "$PROJECT_ID"

# 인증 확인
gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'

# Antigravity CLI 실행
agy
```

CLI 내부에서 Google Cloud project를 선택하고, 대상 프로젝트와 Gemini 모델을 선택한다.

---

## 8. 모델 선택 및 사용 방식

## 8.1 Gemini 모델 사용

Antigravity CLI에서 Google Cloud project를 선택하면 GCP Agent Platform/Vertex AI에서 제공되는 Gemini 모델을 사용할 수 있다.

일반적인 선택 기준은 다음과 같다.

| 작업 유형 | 권장 모델 성격 |
|---|---|
| 코드 리팩토링, 복잡한 장애 분석, 설계 문서 작성 | 고성능 reasoning 모델 |
| 간단한 코드 수정, 요약, 반복 작업 | 빠른 응답/저비용 모델 |
| 대량 파일 분석, 긴 컨텍스트 작업 | long context 지원 모델 |
| 비용 민감한 반복 실험 | Flash 계열 또는 저비용 모델 |

모델명, 리전, preview 여부, 가격은 변경될 수 있으므로 운영 문서에는 특정 모델명을 하드코딩하기보다 **프로젝트에서 실제 선택 가능한 모델**을 기준으로 갱신한다.

---

## 8.2 모델과 리전 확인

Agent Platform/Vertex AI의 Gemini 모델은 모델별로 지원 위치와 상태가 다를 수 있다.

확인 방법:

1. Google Cloud Console → Agent Platform 또는 Vertex AI → Model Garden으로 이동
2. Gemini 모델 선택
3. 지원 리전, 가격, preview/GA 상태 확인
4. 조직 정책 또는 VPC Service Controls 제한 여부 확인

운영 반영 전에는 최소한 다음 항목을 확인한다.

- 사용할 Gemini 모델명
- 지원 리전 또는 global endpoint 여부
- project quota
- TPM/RPM 또는 유사 요청 한도
- 가격 정책
- 데이터 처리 정책

---

## 9. 비용, 쿼터, 데이터 처리 관점

## 9.1 비용

Google Cloud project 연동 방식은 개인 Google AI Pro/Ultra 구독 한도를 사용하는 방식이 아니다.

| 항목 | Google Cloud project 연동 |
|---|---|
| 과금 단위 | Agent Platform/Vertex AI Gemini 모델 사용량 |
| 청구 위치 | GCP Cloud Billing |
| 무료 개인 구독 필요 여부 | 불필요 |
| 한도 기준 | 프로젝트/리전/모델별 quota |
| 비용 통제 | Budget Alert, quota 제한, IAM 제한, 모델 선택 정책 |

---

## 9.2 쿼터

Antigravity CLI 자체의 개인 플랜 한도와 별개로, Google Cloud project를 선택한 경우에는 GCP 프로젝트의 Agent Platform/Vertex AI quota가 적용된다.

운영 전 확인할 항목:

- 모델별 요청 한도
- 모델별 토큰 한도
- 리전별 quota
- preview 모델 제한
- 조직 정책(Organization Policy)
- VPC Service Controls 사용 여부
- 예산 알림(Budget Alert)
- Cloud Logging/Audit Log 수집 여부

---

## 9.3 데이터 처리

Antigravity CLI는 VM에서 repository와 명령을 읽고 실행하지만, 모델 응답 생성을 위해 필요한 컨텍스트는 Google Cloud의 Gemini 모델 API로 전송된다.

따라서 다음 보안 정책을 적용한다.

- 민감정보가 포함된 파일은 `.gitignore`, 도구별 ignore 파일, 파일 권한으로 보호
- `.env`, private key, 인증서, DB dump, 운영 kubeconfig를 작업 디렉토리에 방치하지 않기
- 운영 서버에서 직접 실행하는 경우 read-only 계정 또는 제한된 권한 계정 사용
- 파괴적 명령 실행 전 plan/diff 확인
- Git branch 분리 후 작업
- PR 기반 리뷰 적용
- 필요한 경우 VPC Service Controls, Cloud Audit Logs, IAM Conditions 검토

---

# 10. 운영 권장 구성

## 10.1 개발/테스트 VM 권장 흐름

```text
GCP Dev VM
→ repo clone
→ Antigravity CLI 설치
→ Google Cloud project 연동
→ branch 생성
→ 코드 수정/테스트
→ diff 검토
→ commit 또는 PR 생성
```

예시:

```bash
cd /path/to/repo

git switch -c feature/antigravity-test

agy

# 작업 후 확인
git status --short
git diff --stat
git diff
```

---

## 10.2 운영 서버 직접 실행 시 제한

운영 서버에서 Antigravity CLI를 직접 실행할 수는 있지만 기본 권장 방식은 아니다. 불가피하게 사용한다면 다음 제한을 둔다.

- root 계정 실행 금지
- write 권한이 필요한 디렉토리 최소화
- `systemctl`, `rm`, `chmod`, `chown`, `iptables`, `firewall-cmd`, `kubectl delete`, `terraform apply` 등 위험 명령은 수동 승인
- snapshot/backup 확인 후 작업
- 작업 전 `git status`, `git diff`, `systemctl status`, `df -h` 확인
- 변경 후 rollback 명령 준비
- 작업 로그와 변경 diff 저장

작업 전 확인 예시:

```bash
# Git 상태 확인
git status --short
git branch --show-current

# 시스템 상태 확인
df -h
free -h
systemctl --failed

# 변경 사항 확인
git diff --stat
git diff
```

---

## 10.3 권장 권한 경계

| 대상 | 권장 정책 |
|---|---|
| GCP 프로젝트 | 개발/테스트 전용 프로젝트 분리 |
| VM Service Account | `roles/aiplatform.user` 중심 최소 권한 |
| 사용자 계정 | 직접 모델 호출 권한보다 Service Account Impersonation 우선 |
| Repository | 작업 branch 강제, main 직접 push 금지 |
| 명령 실행 | 파괴적 명령은 수동 확인 후 실행 |
| 비용 | Budget Alert 및 quota 제한 적용 |

---

# 11. Troubleshooting

## 11.1 `agy` 명령을 찾을 수 없음

가능 원인:

- `~/.local/bin`이 `PATH`에 없음
- 설치 스크립트가 shell profile을 갱신했지만 현재 세션에 반영되지 않음
- 설치 실패

확인:

```bash
echo "$PATH"
ls -l ~/.local/bin/agy
export PATH="$HOME/.local/bin:$PATH"
command -v agy
agy --version
```

---

## 11.2 Google Cloud project 선택 후 권한 오류

가능 원인:

- 사용자 또는 VM Service Account에 `roles/aiplatform.user` 권한 없음
- Agent Platform API 비활성화
- Billing 미연결
- 잘못된 프로젝트 선택
- Workspace 또는 조직 정책에서 Google Cloud Platform 접근 제한

확인:

```bash
export PROJECT_ID='YOUR-PROJECT-ID'

gcloud config get-value project
gcloud auth list

gcloud services list --enabled \
  --filter='config.name:aiplatform.googleapis.com' \
  --project "$PROJECT_ID"

gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten='bindings[].members' \
  --filter='bindings.role:roles/aiplatform.user' \
  --format='table(bindings.role,bindings.members)'
```

---

## 11.3 ADC 인증 오류

가능 원인:

- `gcloud auth login`만 수행하고 `gcloud auth application-default login`을 수행하지 않음
- ADC가 다른 계정으로 설정됨
- Service Account Impersonation 권한 부족
- SSH 환경에서 브라우저 인증 미완료

확인:

```bash
gcloud auth list
gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'

# ADC 파일 위치 확인
ls -l ~/.config/gcloud/application_default_credentials.json
```

해결 예시:

```bash
gcloud auth application-default revoke

gcloud auth application-default login
```

Service Account Impersonation 사용 시:

```bash
gcloud auth application-default login \
  --impersonate-service-account="$SA_EMAIL"
```

---

## 11.4 모델 호출 실패 또는 모델이 보이지 않음

가능 원인:

- 선택한 프로젝트에서 Gemini 모델 사용 불가
- 해당 모델이 현재 리전 또는 endpoint에서 미지원
- preview 모델 접근 권한 없음
- quota 부족
- 조직 정책 또는 VPC Service Controls 제한

확인 항목:

```bash
# 프로젝트 확인
gcloud config get-value project

# API 활성화 확인
gcloud services list --enabled \
  --filter='config.name:aiplatform.googleapis.com' \
  --project "$PROJECT_ID"

# quota 확인은 Console의 IAM & Admin / Quotas 또는 Agent Platform quota 화면에서 확인
```

---

## 11.5 CPU 호환성 또는 설치 실패

Antigravity CLI는 네이티브 바이너리로 설치되므로 오래된 CPU 또는 특수 환경에서는 바이너리 실행 오류가 발생할 수 있다.

확인:

```bash
lscpu
uname -m
agy --version
```

구형 VM 이미지나 오래된 CPU 환경에서 문제가 발생하면 다음을 검토한다.

- 최신 Ubuntu LTS 이미지 사용
- x86_64 최신 CPU feature 지원 VM 타입 사용
- 다른 GCE 머신 타입에서 재현 여부 확인
- Antigravity CLI 공식 issue/forum 확인

---

# 12. 기존 Claude Code 연동 문서와의 차이

| 항목 | Claude Code + Vertex AI | Antigravity CLI + Vertex AI Gemini |
|---|---|---|
| 실행 명령 | `claude` | `agy` |
| 주 모델 | Claude on Agent Platform/Vertex AI | Gemini on Agent Platform/Vertex AI |
| 설치 방식 | 공식 설치 스크립트를 내려받아 검토 후 실행 | 공식 설치 스크립트를 내려받아 검토 후 실행 |
| 인증 선택 | 3rd-party platform → Vertex AI | Google Cloud project 선택 |
| 과금 | GCP Agent Platform의 Claude 모델 사용량 | GCP Agent Platform/Vertex AI의 Gemini 모델 사용량 |
| 핵심 IAM | `roles/aiplatform.user` | `roles/aiplatform.user` |
| 실행 위치 | VM/로컬에서 CLI 실행 | VM/로컬에서 CLI 실행 |
| 모델 호출 위치 | Google Cloud 관리형 Claude API | Google Cloud 관리형 Gemini API |
| 운영 주의점 | 코드 컨텍스트가 모델 API로 전송됨 | 코드 컨텍스트가 모델 API로 전송됨 |

---

# 13. 권장 최종 사용 예시

## 13.1 개인 개발 VM에서 빠른 테스트

```bash
cd /path/to/repo

export PROJECT_ID='YOUR-PROJECT-ID'
gcloud config set project "$PROJECT_ID"

gcloud auth login
gcloud auth application-default login

gcloud auth application-default print-access-token >/dev/null && echo 'ADC OK'

# CLI는 앞의 설치 절차에서 검토 후 설치한 상태를 전제로 한다.
export PATH="$HOME/.local/bin:$PATH"

agy
```

Antigravity CLI에서 다음 흐름을 선택한다.

```text
Use Google Cloud project
→ 프로젝트 선택
→ Gemini 모델 선택
→ 작업 시작
```

---

## 13.2 팀/운영형 개발 VM 권장 예시

```bash
cd /path/to/repo

export PROJECT_ID='YOUR-PROJECT-ID'
export SA_NAME='antigravity-cli-sa'
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

# ADC가 Service Account를 impersonate하도록 설정
gcloud auth application-default login \
  --impersonate-service-account="$SA_EMAIL"

gcloud auth application-default print-access-token >/dev/null && echo 'ADC impersonation OK'

# Antigravity CLI 실행
agy
```

이 구성은 다음 장점이 있다.

- 사용자별 Google 로그인은 유지하되 실제 모델 호출 권한은 Service Account로 통제
- IAM 변경/회수 시 사용자별 권한보다 관리가 쉬움
- 장기 Service Account Key JSON 불필요
- Audit Log에서 권한 사용 추적이 상대적으로 명확함

---

# 14. 참고 문서

- Antigravity CLI 설치: https://antigravity.google/docs/cli/install
- Antigravity CLI 시작 가이드: https://antigravity.google/docs/cli/getting-started
- Antigravity and Gemini Enterprise Agent Platform: https://antigravity.google/docs/enterprise
- Google Cloud Agent Platform 시작 가이드: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start
- Agent Platform 인증: https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/authentication
- Gemini Enterprise Agent Platform 제품 개요: https://cloud.google.com/products/gemini-enterprise-agent-platform
- Gemini CLI에서 Antigravity CLI 전환 공지: https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
