# Life Bookshelf AI

인생책장 서비스의 AI 서버 레포지토리

## 프로젝트 구조

- **flows** (AI 로직)
  - autobiographies
    - standard
      - **generate_autobiography** (유지)
  - interviews
    - chat
      - **interview_chat_v2** (Redis 세션 + 신규 알고리즘)
    - standard
      - **generate_interview_questions_v2** (질문 생성 유틸)

- **serve** (API 서버)
  - **session_manager.py** (Redis 세션 관리)
  - autobiographies
    - **generate_autobiography** (유지)
  - interviews
    - **interview_chat_v2** (Redis 기반 세션 관리)

### 폐기된 API (v2.0.0)
- **generate_correction** (교정/교열 기능 불필요)
- **generate_chapter** (덩어리 묶음방식 채택)
- **generate_interview_question** (메인 질문 미리 생성 방식 미채택)
- **interview_chat_v1** (현재 사용 알고리즘 아님)

### 주요 기능 (v2.0.0)
- **지능형 인터뷰**: AI가 사용자의 답변을 분석하여 맞춤형 질문 생성
- **세션 기반 대화**: Redis를 활용한 지속적인 대화 상태 관리
- **자동 자서전 생성**: 인터뷰 내용을 바탕으로 완성된 자서전 작성
- **다양한 주제 지원**: 가족, 학업, 직업, 취미 등 다양한 삶의 영역 커버
- **6W 분석**: 누가/언제/어디서/무엇을/왜/어떻게 축으로 체계적 질문 구성

### 기술적 특징
- **모듈화된 아키텍처**: Flows(로직) + Serve(API) 분리 구조
- **비동기 처리**: FastAPI + async/await로 동시 요청 처리
- **지능형 매칭**: LLM 기반 소재 자동 매칭 및 분석

## 개발 환경 설정

### 전체 시스템 요구사항
- Python 3.9 이상
- Redis Server (6.0 이상)
- OpenAI API Key 또는 Azure OpenAI API Key

## Flows 개발 환경 (AI 로직 개발)

### Python 설치

[Python](https://www.python.org/downloads/) (3.9 이상)을 설치합니다.

### Prompt Flow Extension 설치

[Prompt Flow Extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow)을 설치합니다.

### OpenAI API Key 발급

[OpenAI API Key 발급](https://platform.openai.com/)에서 API Key를 발급받습니다.

[Azure OpenAI API Key 발급](https://ai.azure.com/)에서 API Key를 발급받습니다.

> AZure OpenAI를 활용하는 경우, https://learn.microsoft.com/ko-kr/legal/cognitive-services/openai/limited-access 에서 Azure OpenAI 서비스에 대한 엑세스를 신청해야 할 수 있습니다.

### Basic Setup

```bash
git clone git@github.com:life-librarians/life-bookshelf-ai.git
```

```bash
cd life-bookshelf-ai
```

```bash
code flows/[개발할 플로우 디렉토리]
```

개발할 플로우의 디렉토리를 열기

```bash
python3 -m venv .venv
```

required python3 ≥ `Python 3.9.x` (3.9.x 권장)

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
pip install --upgrade pip
```

![VSCode 인터프리터 설정](image/image1.png)

VSCode에서 인터프리터도 변경해주어야 합니다.

![Prompt Flow Connection 설정](image/image2.png)

Prompt Flow Extension에서 Connection을 설정해줍니다.

![Connection 이름 설정](image/image3.png)
connection 이름을 설정하고 Create Connection 클릭합니다. (다른건 수정 X)

![API 키 입력](image/image4.png)
터미널에서 api_key를 입력하면 connection 등록이 완료됩니다.

> name의 값을 **open_ai_connection** 으로 설정해야 합니다.

### Flow Test Run 실행

![Visul Editor 열기](image/image5.png)

**[실행을 원하는 플로우 경로]/flow.dag.yaml** 파일을 열어 Visual Editor를 실행해줍니다.

![Test Run 실행](image/image6.png)

Test Run을 실행해줍니다.

![실행 결과](image/image7.png)

터미널에서 결과를 확인할 수 있습니다.

![웹 실행 결과](image/image8.png)
또한 제공되는 링크를 열어 웹에서도 결과를 확인할 수 있습니다.

### Flow Batch Run 실행

![Batch Run 실행](image/image9.png)

Batch Run을 실행해줍니다.
Batch Run은 미리 준비한 데이터를 이용하여 여러번의 Test Run을 실행하는 것입니다.

![Local File 선택](image/image10.png)

Local File을 선택합니다.

![data.json 선택](image/image12.png)

**data.json** 파일을 선택합니다.

![Batch Run 실행](image/image13.png)

Batch Run을 실행합니다.

![웹 결과 확인](image/image14.png)

웹에서 결과를 확인할 수 있습니다.

## Serve 개발 환경 (API 서버 개발)

### Python 설치

[Python](https://www.python.org/downloads/) (3.9 이상)을 설치합니다.

```bash
git clone git@github.com:life-librarians/life-bookshelf-ai.git
```

```bash
cd life-bookshelf-ai
```

```bash
code serve
```

개발할 serve 디렉토리를 열기

```bash
python3 -m venv .venv
```

required python3 ≥ `Python 3.9.x` (3.9.x 권장)

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env.development
```

`.env.development` 파일을 생성합니다.

```.env.example
DEBUG=True
LOG_LEVEL=DEBUG

# Azure OpenAI의 API Key를 사용하는 경우
# AZURE_OPENAI_API_KEY=your-api-key
# AZURE_OPENAI_API_BASE=https://your-api-base.openai.azure.com
# AZURE_OPENAI_API_TYPE=azure

# OpenAI의 API Key를 사용하는 경우
AZURE_OPENAI_API_KEY=sk-your-api-key
LIFE_BOOKSHELF_AI_JWT_SECRET_KEY=0190ab45-7e42-7a3f-9dec-726ddf778076
```

자신의 API Key를 입력합니다.

```bash
python -m uvicorn main:app --env-file .env.development --port 3000
```

3000 포트에서 fastapi 서버를 실행합니다.

![서버 실행 예시](image/image15.png)

서버가 정상적으로 실행되었을 경우 위와 같은 로그가 출력됩니다. (실제 로그는 3000포트로 출력됩니다.)

http://localhost:3000/docs 에서 API 문서를 확인할 수 있습니다. (사용 방법 참고: [Life Bookshelf Server](https://github.com/life-librarians/life-bookshelf-server?tab=readme-ov-file#swagger-%EC%9D%B4%EC%9A%A9-%EB%B0%A9%EB%B2%95))

### Redis 설치 및 실행

```bash
# Windows (Chocolatey)
choco install redis-64
redis-server

# 또는 Docker
docker run -d -p 6379:6379 redis:alpine
```

### API 테스트

Swagger UI에서 다음 주요 엔드포인트들을 테스트할 수 있습니다:

- `POST /interviews/start` - 인터뷰 세션 시작
- `POST /interviews/chat` - 인터뷰 대화 진행
- `POST /interviews/end` - 인터뷰 세션 종료
- `POST /autobiographies/generate/{autobiography_id}` - 자서전 생성

## 핵심 기능 상세

### Interview Chat V2 - 지능형 인터뷰 시스템

**개요**: 사용자와의 대화를 통해 점진적으로 삶의 이야기를 수집하고, AI가 답변을 분석하여 다음 질문을 지능적으로 생성하는 시스템입니다.

**주요 특징**:
- 사용자 답변 내용 자동 분석 및 소재 매칭
- 6W 축(Who/When/Where/What/Why/How) 기반 체계적 질문
- 대화 맥락을 고려한 자연스러운 질문 전개
- Redis 기반 세션 지속성 보장

### 통합된 구조

```
flows/interviews/chat/interview_chat_v2/
  - flow.dag.yaml               # 단일 노드 플로우
  - __init__.py                 # 통합 엔진 (Redis 연동)
  - engine/                     # 질문 생성 알고리즘 엔진
    - core.py                   # 기존 알고리즘 + 모델
    - utils.py                  # 기존 유틸 + V2 추가
    - generators.py             # V2 질문 생성
  - data/
    - material.json, theme.json

serve/
  - session_manager.py          # Redis 세션 관리
  - interviews/interview_chat_v2/
    - router/__init__.py        # API 엔드포인트
    - dto/__init__.py           # 요청/응답 스키마
```

### 자서전 생성 시스템

**개요**: 인터뷰를 통해 수집된 사용자의 이야기를 바탕으로 완성된 자서전을 자동 생성하는 시스템입니다.

**주요 특징**:
- 테마와 카테고리 기반 맞춤형 자서전 생성
- 자동 제목 생성 및 내용 구성
- 비동기 처리로 빠른 응답 속도
- 사용자 정보와 인터뷰 내용을 유기적으로 결합

### API 엔드포인트 개요

| 기능 | 엔드포인트 | 설명 |
|------|------------|------|
| 인터뷰 시작 | `POST /interviews/start` | 새로운 인터뷰 세션 시작 |
| 인터뷰 대화 | `POST /interviews/chat` | 사용자 답변 처리 및 다음 질문 생성 |
| 인터뷰 종료 | `POST /interviews/end` | 세션 종료 및 최종 데이터 반환 |
| 자서전 생성 | `POST /autobiographies/generate/{id}` | 인터뷰 기반 자서전 생성 |

자세한 API 사용법 및 명세는 [TEST_GUIDE.md](serve/TEST_GUIDE.md) 참고

## 문서 및 가이드

### 개발 가이드
- **[API 테스트 가이드](serve/TEST_GUIDE.md)** - Swagger UI를 활용한 전체 API 테스트 시나리오
- **[폐기된 API 목록](serve/DEPRECATED_APIS.md)** - v2.0.0에서 제거된 API 목록 및 대체 방안
- **[변경 내역](CHANGELOG.md)** - 버전별 주요 변경사항 및 업데이트 내역

## 기여 및 개발 참여

### 개발 환경 설정
1. 위의 "개발 환경 설정" 섹션 따라 환경 구성
2. `ai/dev` 브랜치에서 작업 시작
3. 기능 개발 후 `ai/prod`로 PR 생성

### 코드 기여 가이드라인
- **코드 스타일**: PEP 8 파이썬 코딩 컨벤션 준수
- **테스트**: 새로운 기능 추가 시 반드시 테스트 코드 작성
- **문서화**: API 변경 시 관련 문서 업데이트 필수
- **커밋 메시지**: 프로젝트 루트의 [COMMIT_CONVENTION.md](../COMMIT_CONVENTION.md) 준수
