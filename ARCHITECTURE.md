# Life Bookshelf AI - 아키텍처 문서

## 1. 프로젝트 개요

**Life Bookshelf AI**는 사용자의 삶 이야기를 인터뷰 방식으로 수집하고, AI가 이를 바탕으로 자서전을 자동 생성해주는 서비스의 AI 서버입니다.

- **런타임**: Python 3.9+, FastAPI, PromptFlow
- **메시지 브로커**: RabbitMQ (비동기 작업 분산)
- **세션 저장소**: Redis (인터뷰 대화 상태 관리)
- **AI 백엔드**: OpenAI / Azure OpenAI
- **음성 처리**: AWS Transcribe (STT), AWS Polly (TTS)

---

## 2. 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        AI Server (FastAPI)                    │
│                                                              │
│  ┌────────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │ Interview Chat │  │ Autobiography  │  │ Voice (TTS/STT)│  │
│  │ V2 Router      │  │ Generate Router│  │ Router         │  │
│  └───────┬────────┘  └───────┬───────┘  └───────┬────────┘  │
│          │                   │                   │           │
│  ┌───────▼────────┐  ┌───────▼───────┐  ┌───────▼────────┐  │
│  │ PromptFlow     │  │ PromptFlow    │  │ AWS Transcribe │  │
│  │ (chat flow)    │  │ (autobiography │  │ Streaming      │  │
│  └───────┬────────┘  │  flow)        │  └────────────────┘  │
│          │           └───────┬───────┘                       │
│  ┌───────▼────────┐          │                               │
│  │ Redis          │  ┌───────▼───────┐                       │
│  │ (Session State)│  │ stream/       │                       │
│  └────────────────┘  │ __init__.py   │ (MQ Producer)         │
│                      └───────┬───────┘                       │
└──────────────────────────────┼───────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │     RabbitMQ        │
                    │  (Message Broker)   │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                       │
┌───────▼────────┐  ┌──────────▼──────────┐  ┌───────▼────────┐
│autobiography.   │  │interview.summary.   │  │interview.meta. │
│trigger.queue    │  │queue                │  │exchange        │
└───────┬────────┘  └──────────┬──────────┘  └───────┬────────┘
        │                      │                       │
┌───────▼────────┐  ┌──────────▼──────────┐           │
│ Autobiography  │  │ InterviewSummary     │     (Backend 서버)
│ Consumer       │  │ Consumer             │
└───────┬────────┘  └──────────┬──────────┘
        │                      │
        └──────────┬───────────┘
                   │
          ┌────────▼────────┐
          │ stream/         │
          │ __init__.py     │ (MQ Producer → 결과 publish)
          └─────────────────┘
```

---

## 3. 디렉토리 구조

```
ai/
├── flows/                          # AI 로직 (PromptFlow)
│   ├── interviews/
│   │   ├── chat/
│   │   │   └── interview_chat_v2/  # 인터뷰 대화 플로우
│   │   └── standard/
│   │       └── generate_interview_questions_v2/
│   ├── autobiographies/
│   │   └── standard/
│   │       └── generate_autobiography/ # 자서전 생성 플로우
│   └── interview_summary/
│       └── standard/
│           └── summarize_interview/    # 인터뷰 요약 플로우
│
└── serve/                          # API 서버
    ├── main.py                     # FastAPI 앱 진입점
    ├── session_manager.py          # Redis 세션 관리
    ├── constants.py                # Enum 상수 정의
    ├── stream/                     # [핵심] 메시지 스트리밍 모듈
    │   ├── __init__.py             # MQ Producer (publish 함수들)
    │   ├── dto/__init__.py         # 메시지 페이로드 Pydantic 모델
    │   └── consumers/
    │       ├── __init__.py         # Consumer 스레드 시작 관리자
    │       ├── autobiography_consumer.py
    │       └── interview_summary_consumer.py
    ├── interviews/
    │   ├── interview_chat_v2/      # 인터뷰 채팅 API
    │   └── interview_summary/      # 인터뷰 요약 API
    ├── autobiographies/
    │   └── generate_autobiography/ # 자서전 생성 API
    └── voice/                      # 음성 API (TTS/STT)
```

---

## 4. Stream 모듈 상세 (`serve/stream/`)

> 이 프로젝트의 핵심 비동기 메시징 레이어입니다. RabbitMQ를 통해 AI 처리 결과를 Backend 서버로 전달하고, 외부 트리거 메시지를 소비합니다.

### 4.1 전체 흐름

```
[HTTP 요청 처리]               [MQ 소비]
       │                           │
       ▼                           ▼
 stream/__init__.py          consumers/__init__.py
 (Publisher)                 (start_all_consumers)
       │                           │
  publish_*()               daemon thread 2개
       │                    ├── InterviewSummaryConsumer
       ▼                    └── AutobiographyConsumer
  RabbitMQ Exchange
```

---

### 4.2 `stream/__init__.py` - MQ Producer

AI 처리 결과를 RabbitMQ Exchange로 publish하는 함수 모음입니다. 모든 함수는 환경변수에서 RabbitMQ 접속 정보를 읽고, **매 호출마다 새 커넥션을 열고 닫습니다.**

| 함수 | Exchange | Routing Key | 용도 |
|------|----------|-------------|------|
| `publish_persistence_message` | `ai.request.exchange` | `ai.persistence` | 인터뷰 Q&A를 Backend DB에 저장 요청 |
| `publish_categories_message` | `interview.meta.exchange` | `interview.meta` | 카테고리/청크/소재 변경사항 전송 |
| `publish_generated_autobiography` | `autobiography.trigger.exchange` | `autobiography.trigger.result` | 생성된 자서전 결과 전송 |
| `publish_result_to_aggregator` | `autobiography.trigger.exchange` | `autobiography.trigger.cycle.result` | 사이클 단위 완료 결과를 Aggregator로 전송 |
| `publish_interview_summary_result` | `interview.summary.exchange` | `interview.summary.result` | 인터뷰 요약 결과 전송 |

**주요 특징:**
- 모든 메시지는 `delivery_mode=2` (디스크 영속성)
- Pydantic 모델의 `model_dump_json()`으로 직렬화
- 실패 시 예외를 re-raise하여 호출부에서 처리

---

### 4.3 `stream/dto/__init__.py` - 페이로드 모델

RabbitMQ 메시지의 스키마를 Pydantic으로 정의합니다.

```
InterviewPayload               → publish_persistence_message 에서 사용
  ├── autobiographyId: int
  ├── userId: int
  ├── conversation: [Conversation]
  │     ├── content: str
  │     ├── conversationType: str  # "BOT" | "HUMAN"
  │     └── materials: str         # JSON 문자열 (material ID 배열)
  └── interviewQuestion: InterviewQuestion
        ├── questionText: str
        ├── questionOrder: int
        └── materials: str

CategoriesPayload              → publish_categories_message 에서 사용
  ├── autobiographyId, userId, themeId, categoryId
  ├── chunks: [ChunksPayload]
  └── materials: [MaterialsPayload]

InterviewAnswersPayload        → AutobiographyConsumer가 수신하는 형태
  ├── cycleId: str (Optional)
  ├── step: int
  ├── autobiographyId, userId
  ├── userInfo: UserInfo         # gender, occupation, ageGroup
  ├── autobiographyInfo: AutobiographyInfo  # theme, reason, category
  └── answers: [InterviewAnswer]

GeneratedAutobiographyPayload  → publish_generated_autobiography 에서 사용
  ├── cycleId, step (Optional)
  ├── autobiographyId, userId
  ├── title: str
  └── content: str

InterviewSummaryResponsePayload → publish_interview_summary_result 에서 사용
  ├── interviewId, userId
  └── summary: str
```

---

### 4.4 `stream/consumers/__init__.py` - Consumer 시작 관리자

FastAPI 앱 임포트 시 `start_all_consumers()`가 즉시 실행되며, 두 개의 **daemon 스레드**를 시작합니다.

```python
# main.py 에서 import 만으로 자동 실행
import stream.consumers
```

```
start_all_consumers()
│
├── 환경변수 체크 (RABBITMQ_HOST, USER, PASSWORD)
│   └── 미설정 시 경고 후 skip
│
├── threading.Thread(target=start_interview_summary_consumer, daemon=True)
│   └── InterviewSummaryConsumer().start_consuming()
│       └── queue: interview.summary.queue
│
└── threading.Thread(target=start_autobiography_consumer, daemon=True)
    └── AutobiographyConsumer().start_consuming()
        └── queue: autobiography.trigger.queue
```

- `daemon=True`: 메인 프로세스(FastAPI) 종료 시 자동으로 함께 종료
- 각 스레드는 독립적으로 실패해도 다른 스레드에 영향 없음

---

### 4.5 `AutobiographyConsumer` - 자서전 생성 컨슈머

**구독 큐**: `autobiography.trigger.queue`

**처리 흐름:**

```
[RabbitMQ 메시지 수신]
        │
        ▼
  on_message()
  ├── action == "merge" → basic_nack (requeue=False, 무시)
  ├── cycleId 없음 → basic_nack (requeue=False, 거부)
  └── 정상 메시지
        │
        ▼
  consume_interview_answers(payload)
  ├── InterviewAnswersPayload 역직렬화
  ├── PromptFlow 실행
  │     flow_path = flows/autobiographies/standard/generate_autobiography/flow.dag.yaml
  │     입력: user_info, autobiography_info, interviews[], autobiography_id
  │     출력: {"title": "...", "autobiographical_text": "..."}
  │
  └── GeneratedAutobiographyPayload 생성
        │
        ├── publish_result_to_aggregator()
        │     → autobiography.trigger.exchange / autobiography.trigger.cycle.result
        │
        └── publish_generated_autobiography()
              → autobiography.trigger.exchange / autobiography.trigger.result
        │
        ▼
  basic_ack (성공) / basic_nack requeue=False (실패)
```

**특이사항:**
- PromptFlow 출력이 Generator일 경우 `''.join()`으로 합산
- JSON 파싱 실패 시 raw 텍스트를 content로 사용 (폴백 처리)

---

### 4.6 `InterviewSummaryConsumer` - 인터뷰 요약 컨슈머

**구독 큐**: `interview.summary.queue`

**처리 흐름:**

```
[RabbitMQ 메시지 수신]
        │
        ▼
  on_message()
  └── InterviewSummaryRequestDto 역직렬화
        │
        ▼
  consume_interview_summary(request_dto)
  ├── PromptFlow 실행
  │     flow_path = flows/interview_summary/standard/summarize_interview/flow.dag.yaml
  │     입력: conversation[] (model_dump 리스트)
  │     출력: {"summary": "..."}
  │
  └── InterviewSummaryResponsePayload 생성
        │
        ▼
  publish_interview_summary_result()
  → interview.summary.exchange / interview.summary.result
        │
        ▼
  basic_ack (성공) / basic_nack requeue=False (실패)
```

---

### 4.7 RabbitMQ Exchange/Queue 전체 맵

```
Exchange                        Routing Key                       발행 주체         소비 주체
──────────────────────────────────────────────────────────────────────────────────────────────
ai.request.exchange             ai.persistence                    AI Server (API)   Backend 서버
interview.meta.exchange         interview.meta                    AI Server (API)   Backend 서버
autobiography.trigger.exchange  autobiography.trigger.result      AutobiographyConsumer  Backend 서버
autobiography.trigger.exchange  autobiography.trigger.cycle.result AutobiographyConsumer Backend Aggregator
interview.summary.exchange      interview.summary.result          InterviewSummaryConsumer Backend 서버
──────────────────────────────────────────────────────────────────────────────────────────────
autobiography.trigger.queue     (← autobiography.trigger.exchange)               AI Server Consumer
interview.summary.queue         (← interview.summary.exchange)                   AI Server Consumer
```

---

## 5. API 엔드포인트

### 5.1 인터뷰 채팅 (`/api/v2/interviews`)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/start/{autobiography_id}` | 인터뷰 세션 시작, 첫 질문 반환 |
| POST | `/chat/{autobiography_id}` | 사용자 답변 처리, 다음 질문 반환 |
| POST | `/end/{autobiography_id}` | 세션 종료, 최종 메트릭 반환 |
| POST | `/{interview_id}/summary` | 인터뷰 대화 요약 생성 |

**인터뷰 채팅 흐름:**
```
POST /start
  → SessionManager.create_session() (Redis)
  → PromptFlow 실행 (첫 질문 생성)
  → publish_persistence_message() (MQ)
  → 첫 질문 반환

POST /chat
  → SessionManager.load_session() (Redis)
  → PromptFlow 실행 (다음 질문 생성)
  → publish_persistence_message() (MQ, 사용자 답변 + AI 질문)
  → 다음 질문 반환

POST /end
  → SessionManager.load_session() (Redis)
  → SessionManager.delete_session() (Redis)
  → final_metrics 반환
```

### 5.2 자서전 생성 (`/api/v2/autobiographies`)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/generate/{autobiography_id}` | 인터뷰 기반 자서전 직접 생성 (동기) |

> 동기 HTTP 엔드포인트 외에, RabbitMQ를 통한 **비동기 자서전 생성**도 지원합니다 (`AutobiographyConsumer`).

### 5.3 음성 (`/api/v2/voice`)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/voice/tts` | 텍스트 → 음성 (AWS Polly), MP3 StreamingResponse |
| POST | `/voice/stt` | 음성 파일 → 텍스트 (AWS Transcribe) |
| WS | `/voice/stt/stream` | **실시간 WebSocket 스트리밍 STT** (AWS Transcribe Streaming) |

---

## 6. 실시간 음성 STT 스트리밍 (`voice/streaming_stt.py`)

WebSocket을 통해 음성 청크를 실시간으로 받아 AWS Transcribe Streaming으로 전달합니다.

```
Client (WebSocket)
      │ bytes 청크 전송
      ▼
voice/router: /stt/stream
      │
      ▼
stream_transcribe(audio_generator)
  ├── TranscribeStreamingClient 연결 (ap-northeast-2, ko-KR, 16000Hz PCM)
  ├── asyncio.gather(write_chunks(), handler.handle_events())
  │     ├── write_chunks(): 오디오 청크를 Transcribe input_stream으로 전달
  │     └── handle_events(): Transcribe 결과 수신
  │           └── is_partial=False인 결과만 저장 (최종 인식 결과)
  └── 합산된 transcript 반환
      │
      ▼
WebSocket으로 {"transcript": "..."} 응답
```

**핵심 구성요소:**
- `StreamHandler`: `TranscriptResultStreamHandler` 상속, 최종 인식 결과만 수집
- `stream_transcribe()`: 비동기 오디오 스트림을 받아 실시간 인식 후 전체 텍스트 반환

---

## 7. Redis 세션 관리 (`session_manager.py`)

인터뷰 대화 상태를 Redis에 영구 저장합니다 (TTL 없음).

**세션 키 형식**: `session:{userId}:{autobiographyId}`

**저장 데이터:**
```json
{
  "metrics": {
    "session_id": "1:100",
    "user_id": 1,
    "autobiography_id": 100,
    "preferred_categories": [],
    "asked_total": 5
  },
  "last_question": { ... },
  "updated_at": 1234567890.0
}
```

| 메서드 | 설명 |
|--------|------|
| `create_session()` | 새 세션 또는 이전 메트릭 기반 세션 생성 |
| `save_session()` | 세션 상태 저장/갱신 |
| `load_session()` | 세션 로드 |
| `delete_session()` | 세션 삭제 (인터뷰 종료 시) |
| `get_session_for_flow()` | PromptFlow 입력 형식으로 변환 |
| `extract_user_id_from_token()` | JWT에서 userId 추출 |

---

## 8. 인증 (`auth`)

JWT 기반 인증. `AuthRequired()` Depends로 FastAPI 라우터에 적용합니다.

```python
@router.post("/chat/{autobiography_id}", dependencies=[Depends(AuthRequired())])
```

JWT Secret Key: 환경변수 `LIFE_BOOKSHELF_AI_JWT_SECRET_KEY`

---

## 9. 환경변수

```env
# AI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_BASE=...
AZURE_OPENAI_API_VERSION=2023-07-01-preview

# RabbitMQ
RABBITMQ_HOST=...
RABBITMQ_PORT=5672
RABBITMQ_USER=...
RABBITMQ_PASSWORD=...

# Redis
REDIS_HOST=...
REDIS_PORT=6379

# Auth
LIFE_BOOKSHELF_AI_JWT_SECRET_KEY=...

# AWS (Voice)
AWS_REGION=ap-northeast-2

# CORS
WEB_URL=https://...
```

---

## 10. 시작 순서

```
uvicorn main:app 실행
    │
    ├── create_connection()       # PromptFlow용 OpenAI 커넥션 등록
    ├── FastAPI 라우터 등록
    ├── import stream.consumers   # 자동으로 start_all_consumers() 실행
    │     ├── InterviewSummaryConsumer (daemon thread)
    │     └── AutobiographyConsumer (daemon thread)
    └── HTTP 서버 시작 (port 3000)
```
