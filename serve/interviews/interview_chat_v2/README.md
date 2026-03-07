# Interview Chat V2 API

소재 매칭 기반 체계적 질문 생성 시스템

## Redis 세션 기반 아키텍처

```
[백엔드] --session/start-----> [AI 서버]
      (sessionId + metrics)     ↓
                           [Redis에 세션 생성]
                                ↓
                           [Legacy 엔진 초기화]
                                ↓
[백엔드] <--first_question----- [AI 서버]

[백엔드] --interview-chat----> [AI 서버]
      (sessionId + answer)      ↓
                           [Redis에서 세션 로드]
                                ↓
                           [엔진 상태 복원]
                                ↓
                           [답변 분석 + 메트릭 업데이트]
                                ↓
                           [소재 선택 + 질문 생성]
                                ↓
                           [Redis에 상태 저장]
                                ↓
[백엔드] <--next_question------ [AI 서버]
```

### 주요 변경사항
- **Redis 세션 관리**: 대화 상태를 Redis에 저장하여 TTL 1시간 지속성 보장
- **단일 노드 플로우**: 복잡한 노드 체인을 하나로 통합
- **Legacy 알고리즘 통합**: 기존 질문 생성 알고리즘 완전 통합

## 엔드포인트

### 1. 세션 시작 (Redis 세션 생성)
`POST /interviews/start`

### 2. 대화 진행 (Redis 기반 상태 관리)
`POST /interviews/chat`

### 3. 세션 종료 (최종 메트릭 수집)
`POST /interviews/end`

## 세션 시작 요청 예시

### 새 세션 시작
```json
{
  "sessionId": "sess-001"
}
```

### 선호 카테고리 지정
```json
{
  "sessionId": "sess-001",
  "preferredCategories": [3, 5]
}
```

### 세션 재개 (이전 메트릭 포함)
```json
{
  "sessionId": "sess-001",
  "previousMetrics": {
    "sessionId": "sess-001",
    "categories": {
      "cat_1": {
        "category_num": 1,
        "category_name": "부모",
        "chunks": {
          "chunk_1": {
            "chunk_num": 1,
            "chunk_name": "프로파일",
            "materials": {
              "mat_1": {
                "material_num": 1,
                "material_name": "성격",
                "w": [1, 1, 0, 1, 0, 0],
                "ex": 1,
                "con": 0,
                "material_count": 0
              }
            }
          }
        },
        "chunk_weight": {"1": 5}
      }
    },
    "engine_state": {
      "last_material_id": [1, 1, 1],
      "last_material_streak": 2,
      "epsilon": 0.1
    },
    "asked_total": 5
  }
}
```

## 세션 시작 응답 예시

### 새 세션 (카테고리 소개 질문)
```json
{
  "sessionId": "sess-001",
  "first_question": {
    "id": "q-48b8",
    "material": "일반_소개",
    "type": "category_intro",
    "text": "어떤 이야기를 하고 싶으신가요? 기억에 남는 에피소드나 경험이 있다면 들려주세요.",
    "material_id": [0, 0, 0]
  }
}
```

### 선호 카테고리 지정 시
```json
{
  "sessionId": "sess-001",
  "first_question": {
    "id": "q-d423",
    "material": "형제, 친첵_소개",
    "type": "category_intro",
    "text": "형제, 친첵에 대해서 어떤 이야기를 하고 싶으신가요?",
    "material_id": [3, 0, 0]
  }
}
```

## 대화 진행 요청 예시 (간소화)

```json
{
  "sessionId": "sess-001",
  "answer_text": "저는 내성적인 성격이에요. 사람들과 어울리는 것보다는 혼자 있는 시간을 더 좋아하고..."
}
```

**주요 변경**: question, question_pool, use_llm_keywords 필드 제거로 API 간소화

## 대화 진행 응답 예시

### 동일 소재 계속 질문
```json
{
  "next_question": {
    "id": "q-def456",
    "material": "성격",
    "type": "ex",
    "text": "본인의 화를 잘 내는 성격과 관련된 사건이 있나요?",
    "material_id": [1, 1, 1]
  }
}
```

### 다른 소재로 전환
```json
{
  "next_question": {
    "id": "q-abc789",
    "material": "금융",
    "type": "when",
    "text": "금융에 대해 '언제' 측면에서 더 구체적으로 들려주세요.",
    "material_id": [5, 2, 3]
  }
}
```

## 세션 종료 요청 예시

```json
{
  "sessionId": "sess-001"
}
```

## 세션 종료 응답 예시

```json
{
  "sessionId": "sess-001",
  "final_metrics": {
    "sessionId": "sess-001",
    "categories": {
      "cat_1": {
        "category_num": 1,
        "category_name": "부모",
        "chunks": {
          "chunk_1": {
            "chunk_num": 1,
            "chunk_name": "프로파일",
            "materials": {
              "mat_1": {
                "material_num": 1,
                "material_name": "성격",
                "w": [1, 1, 1, 0, 1, 1],
                "ex": 1,
                "con": 1,
                "material_count": 1
              }
            }
          }
        },
        "chunk_weight": {"1": 15}
      }
    },
    "engine_state": {
      "last_material_id": [1, 1, 1],
      "last_material_streak": 3,
      "epsilon": 0.1
    },
    "asked_total": 10
  },
  "pool_to_save": []
}
```

## Redis 세션 관리

### TTL 기반 자동 만료
- **세션 TTL**: 1시간 (3600초)
- **자동 정리**: Redis가 만료된 세션 자동 삭제
- **세션 연장**: 대화 진행 시 자동으로 TTL 연장

### 세션 데이터 구조
```json
{
  "metrics": {
    "sessionId": "sess-001",
    "categories": { /* 직렬화된 엔진 상태 */ },
    "engine_state": {
      "last_material_id": [1, 1, 1],
      "last_material_streak": 2,
      "epsilon": 0.1
    },
    "asked_total": 5
  },
  "last_question": {
    "id": "q-abc123",
    "material": "성격",
    "type": "w2",
    "text": "...",
    "material_id": [1, 1, 1]
  },
  "updated_at": 1640995200.0
}
```

## 백엔드 처리 (간소화)

### 세션 시작
1. `sessionId`와 선택적 `preferredCategories` 또는 `previousMetrics`를 AI 서버로 전달
2. AI 서버가 Redis에 세션 생성 및 `first_question` 반환
3. 백엔드는 사용자에게 첫 질문 전달

### 대화 진행
1. `sessionId`와 `answer_text`만 AI 서버로 전달 (간소화)
2. AI 서버가 Redis에서 세션 로드, 엔진 처리, 상태 저장
3. `next_question`을 사용자에게 전달

### 세션 종료
1. `sessionId`로 AI 서버에 세션 종료 요청
2. AI 서버가 Redis에서 최종 메트릭 조회 및 세션 삭제
3. `final_metrics`를 백엔드에 반환하여 DB 저장

**대체 방안**: Redis TTL(1시간)로 자동 만료 처리 가능

## 주요 변경사항 (v2)

### Redis 세션 관리 도입
- **세션 지속성**: Redis TTL 1시간으로 대화 상태 보장
- **상태 복원**: 세션 재개 시 이전 메트릭 자동 복원
- **자동 정리**: TTL 만료로 세션 자동 삭제

### Legacy 알고리즘 통합
- **완전 통합**: 기존 질문 생성 알고리즘 100% 보존
- **파일 통합**: 7개 파일을 3개로 통합하여 구조 개선
- **코드 보존**: `#기존 알고리즘` 주석으로 Legacy 개발자 친화적

### API 간소화
- **요청 간소화**: sessionId + answer_text만 전달
- **내부 상태 관리**: AI 서버가 Redis로 상태 관리
- **session/end 제거**: Redis TTL로 자동 만료 처리
