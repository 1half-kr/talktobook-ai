# Interview Chat V2 Flow

Legacy 알고리즘 기반 체계적 질문 생성 플로우

## 통합된 구조 개요

```
interview_chat_v2/
├── engine/                   # Legacy 알고리즘 엔진 (통합)
│   ├── core.py              # 기존 알고리즘 + 모델 (InterviewEngine, Material, Category)
│   ├── utils.py             # 기존 유틸 + V2 추가 (HINTS, 매칭, 상태복원)
│   └── generators.py        # V2 질문생성 + 테마관리 (LLM 연동, ThemeManager)
├── data/                    # 데이터 파일
│   ├── material.json        # 소재 구조 정의
│   └── theme.json           # 테마 정의
├── __init__.py             # 통합 엔진 (Redis 연동)
├── flow.dag.yaml           # Prompt Flow 정의 (단일 노드)
└── data.json               # 테스트 데이터
```

### 파일 통합 결과
- **7개 → 3개**: constants.py, material_matcher.py, models.py, question_generator.py, state_manager.py, theme.py → core.py, utils.py, generators.py
- **Legacy 코드 보존**: `#기존 알고리즘` 주석으로 기존 개발자가 쉽게 찾을 수 있음
- **V2 추가 기능**: `#V2 추가 함수` 주석으로 신규 기능 구분

## Legacy 알고리즘 통합

### 데이터 구조 (3단계 계층)
```
Category (카테고리) → Chunk (덩어리) → Material (소재)
```

### 핵심 알고리즘
1. **소재 선택 우선순위**:
   - 직전 소재 유지 (streak < 3 AND material_count < 1)
   - ε-greedy 탐색 (10% 랜덤)
   - chunk_weight 내림차순 → progress_score 오름차순

2. **질문 타겟 우선순위**:
   - w2("어떻게") → ex(예시) → con(유사사례) → 나머지 w들

3. **메트릭 시스템**:
   - 6W 원칙: w1~w6 (언제/어떻게/누가/무엇을/어디서/왜)
   - ex: 예시 플래그
   - con: 유사사례 플래그
   - material_count: 소재 완성도 (sum(w) ≥ 3 AND ex==1 AND con==1)

4. **chunk_weight 시스템**:
   - 테마 부스트: 선택된 테마의 chunk들을 10으로 초기화
   - 동일 덩어리 보상: 답변 시 해당 chunk_weight +1

## Redis 세션과 Engine의 관계

**통합 엔진 + Redis 세션 관리**
```python
@tool
def interview_engine(sessionId: str, answer_text: str) -> Dict:
    # 1. Redis에서 세션 로드
    session_data = redis_client.get(f"session:{sessionId}")
    
    # 2. Legacy 엔진 인스턴스 생성/복원
    engine = InterviewEngine(categories)
    restore_categories_state(categories, metrics["categories"])
    
    # 3. 엔진 알고리즘 실행
    engine.update_after_answer(mapped_ids, current_id)
    material_id = engine.select_material()
    
    # 4. Redis에 상태 저장
    redis_client.setex(session_key, 3600, json.dumps(session_update))
    
    return {"next_question": question}
```

단일 노드에서 Redis 세션 관리와 Legacy 엔진을 모두 처리합니다.

## 입력/출력

### 입력
```yaml
sessionId: string
question: object          # {id, material, type}
answer_text: string
metrics: object           # 엔진 상태 (engine_state, categories)
question_pool: array      # 사용 안 함
use_llm_keywords: boolean # 기본: false
```

### 출력
```yaml
next_question: object     # {id, material, type, text, material_id}
```

## 통합 엔진 처리 과정

### 1. 세션 로드 및 엔진 초기화
- **Redis 세션 로드**: 이전 대화 상태 및 메트릭 복원
- **엔진 초기화**: material.json에서 카테고리 구조 로드
- **상태 복원**: 이전 메트릭으로 엔진 상태 복원 (`restore_categories_state`)

### 2. 답변 분석 및 소재 매칭
- **소재 매칭**: material.json의 소재와 답변 텍스트 정확 매칭 (`find_matching_materials`)
- **동일 소재 감지**: 현재 질문한 소재가 답변에 포함되어 있는지 확인
- **6W 축 감지**: HINTS 기반 룰 매칭 (`hit_any`)
- **메트릭 업데이트**: Legacy 알고리즘으로 6W 축, ex/con 플래그 업데이트

### 3. 질문 생성 및 세션 저장
- **소재 선택**: Legacy 알고리즘으로 다음 소재 선택 (`select_material`)
- **질문 타겟 선택**: 소재 내 질문 타겟 선택 (`select_question_in_material`)
- **LLM 질문 생성**: 컨텍스트 기반 질문 생성 (`generate_question_llm`)
- **Redis 저장**: 업데이트된 상태를 Redis에 저장

## 핵심 개선사항

### 소재 매칭 방식 변경
- **이전**: 키워드 추출 → 소재 매핑
- **현재**: material.json의 정확한 소재명과 답변 텍스트 매칭

### 질문 생성 로직
- **동일 소재 (same_material=true)**: 답변 내용 그 자체를 반영한 질문
- **다른 소재 (same_material=false)**: material + type만으로 LLM 질문 생성

### 엔진 초기화 안정성
- material.json 로드 실패 시 적절한 에러 처리
- 엔진 상태 복원 로직 개선

## 테스트

```bash
# VSCode에서 flow.dag.yaml 열기
# Visual Editor → Test Run 실행
# data.json의 테스트 데이터 사용
```

## 종료 조건

```python
(충분히 채워진 소재 ≥ 30) AND (카테고리 커버리지 ≥ 70% OR 원고 길이 ≥ 37,500자)
```

## 주요 특징

### 통합 및 최적화
- ✅ **파일 통합**: 7개 파일을 3개로 통합하여 구조 단순화
- ✅ **Legacy 코드 보존**: `#기존 알고리즘` 주석으로 기존 개발자 친화적
- ✅ **Redis 세션 관리**: 대화 상태 지속성 보장
- ✅ **단일 노드 플로우**: 복잡한 노드 체인을 하나로 통합

### Legacy 알고리즘 완전 통합
- ✅ **3단계 계층 구조**: Category → Chunk → Material
- ✅ **ε-greedy 탐색**: 10% 랜덤 탐색으로 다양성 확보
- ✅ **chunk_weight 시스템**: 테마 부스트 + 답변 보상
- ✅ **streak 관리**: 같은 소재 최대 3회 연속 질문
- ✅ **정교한 우선순위**: chunk_weight DESC → progress_score ASC

### V2 개선사항
- ✅ **정확한 소재 매칭**: material.json 기반 정확한 문자열 매칭
- ✅ **컨텍스트 기반 질문**: 동일 소재 시 답변 내용 반영
- ✅ **안정적 엔진**: material.json 로드 및 에러 처리 개선
- ✅ **LLM 연동**: generate_interview_questions_v2 플로우 활용