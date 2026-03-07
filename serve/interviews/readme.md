# Life Bookshelf AI — Interviews v2 (Chat Orchestration + Standard Worker)

이 문서는 **interviews 도메인(v2)** 기준으로, **데이터 계약(Contracts)**, **노드 I/O**, **Prompt Flow 구성**, **서빙 API 스펙**을 한눈에 볼 수 있도록 정리한 README

## 목표 요약

- **chat**: 대화 오케스트레이션 (파싱 → 메트릭 갱신 → 결핍셀 기반 후보 생성 → 질문 선택)
- **standard**: “질문 1문장 생성” 단일 기능 워커 (LLM 템플릿 + 가드)
- **shared(선택)**: 템플릿/생성 유틸의 단일 소스(DRY)

---

## 폴더 구조

~~~text
flows/
  interviews/
    chat/
      interview_chat_v2/
        flow.dag.yaml
        nodes/
          01_parse_answer.py         # 응답 파서
          02_update_metrics.py       # 메트릭 갱신 및 결핍셀 산출
          03_generate_candidates.py  # 결핍셀 기반 질문 후보 생성
          04_select_questions.py     # 질문 선택 알고리즘
    standard/
      generate_interview_question_v2/
        flow.dag.yaml                # LLM 노드 + Guard 노드 (connection 사용)
        prompts/
          ask_question_v2.jinja2     # 질문 템플릿 (Jinja)
        nodes/
          03_guard.py                # 길이/문장부호 보정
    shared/                          # (선택) DRY를 위한 공용 모듈
      prompts/
        ask_question_v2.jinja2
      questions/
        generator.py                 # (선택) 질문 생성 로직의 단일 소스
serve/
  interviews/
    interview_question_v2/
      router.py                      # /api/v2/interviews/interview-questions
      dto/
        request.py
        response.py
~~~

---

## 데이터 모델 (Python Dataclasses)

~~~py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

MaterialId = Tuple[int, int, int]  # (category_num, chunk_num, material_num)

@dataclass
class Material:
    material_num: int                           # 소재 번호 (한 덩어리 내 1..)
    material_name: str                          # 소재 이름(내용)
    w: List[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])  # who..why..when..how..where..what (0/1)
    ex: int = 0                                 # 사례(0/1)
    con: int = 0                                # 유사사례/구체화(0/1)
    material_count: int = 0                     # 완료 플래그(0/1)

    def sum_w(self) -> int:
        return sum(self.w)

    def progress_score(self) -> int:
        return self.sum_w() + self.ex + self.con

    def mark_filled_if_ready(self) -> None:
        if self.sum_w() >= 3 and self.ex == 1 and self.con == 1:
            self.material_count = 1

@dataclass
class Chunk:
    chunk_num: int                               # 덩어리 번호(카테고리 내 1..)
    chunk_name: str                              # 덩어리 이름
    materials: Dict[int, Material] = field(default_factory=dict)

@dataclass
class Category:
    category_num: int                            # 카테고리 번호(전체 1..)
    category_name: str                           # 카테고리 이름
    chunks: Dict[int, Chunk] = field(default_factory=dict)

    # 덩어리 가중치 (없으면 0으로 간주)
    # - 테마 선택 시 해당 카테고리의 모든 chunk_weight = 10
    # - 같은 덩어리 내 대화 진행 시 chunk_weight += 1
    chunk_weight: Dict[int, int] = field(default_factory=dict)

    def ensure_weights(self) -> None:
        for ch_num in self.chunks.keys():
            self.chunk_weight.setdefault(ch_num, 0)

@dataclass
class EngineState:
    last_material_id: Optional[MaterialId] = None  # 직전 소재 식별자
    last_material_streak: int = 0                  # 같은 소재 연속 N회(≥3이면 전환)
    epsilon: float = 0.10                          # ε-greedy 탐색 비율(0.1)
~~~

---

## 데이터 구조(계약, v2)

### 공통
- `MaterialId = [category_num, chunk_num, material_num]` (JSON에서는 리스트로 표기)
- `W 인덱스 순서 = ["who","why","when","how","where","what"]` → `w[0]..w[5]`

### Metrics (세션 상태; 백엔드 저장)

~~~json
{
  "sessionId": "sess-001",
  "theme": "finance",

  "categories": {
    "1": {
      "category_num": 1,
      "category_name": "부모",
      "chunks": {
        "1": {
          "chunk_num": 1,
          "chunk_name": "성격",
          "materials": {
            "1": {
              "material_num": 1,
              "material_name": "출생지",
              "w": [1, 0, 1, 0, 1, 1],
              "ex": 0,
              "con": 0,
              "material_count": 0,
              "utter_freq": 13
            }
          }
        }
      },
      "chunk_weight": { "1": 12 }
    },

    "2": {
      "category_num": 2,
      "category_name": "연인",
      "chunks": {
        "3": {
          "chunk_num": 3,
          "chunk_name": "만남",
          "materials": {
            "2": {
              "material_num": 2,
              "material_name": "끌림/경계 요소",
              "w": [1, 0, 1, 1, 0, 1],
              "ex": 0,
              "con": 0,
              "material_count": 0,
              "utter_freq": 2
            }
          }
        }
      },
      "chunk_weight": { "3": 10 }
    }
  },

  "engine_state": {
    "last_material_id": [1, 1, 1],
    "last_material_streak": 2,
    "epsilon": 0.10
  },

  "asked_total": 7,
  "policyVersion": "v1.2.0"
}
~~~

> **초기화 규칙**  
> - 세션 시작 시, 선택된 `theme`에 해당하는 카테고리의 **모든 하위 chunk_weight = 10**  
> - 답변 반영 시 **같은 덩어리**의 `chunk_weight += 1`

---

### 질문 풀 (Question Pool; 백엔드 저장)

~~~json
[
  {
    "id": "q-48b8",
    "material_id": [2, 3, 2],                 // (category_num, chunk_num, material_num)
    "material_name": "끌림/경계 요소",        // (선택) 디버깅용
    "keywords": ["적금", "첫직장", null],
    "type": "when",                           // who|why|when|how|where|what|ex|con
    "text": "첫 직장 시절 적금을 시작하게 된 계기는 언제였나요?",
    "source": "template+llm",                 // template|llm|template+llm
    "status": "queued",                       // queued|asked|dropped
    "createdAt": "2025-10-05T06:25:00Z"
  }
]
~~~

- (material_id, type) 조합은 **중복 금지**(pool에서 체크).

---

## 노드 I/O 스펙 & 로직

### 노드1: `01_parse_answer.py` — 응답 파서

**입력**
~~~json
{
  "sessionId": "sess-001",
  "question": { "id":"q-47ab", "material_id":[1,1,1], "type":"why" },
  "answerText": "초등학교 때 어머니가...",
  "metrics": { ... }
}
~~~

**출력**
~~~json
{
  "parsed": {
    "material_hits": [[1,1,1]],        // 응답이 언급한 소재(MaterialId 리스트)
    "keywords": ["어머니", "초등학교"],
    "w_evidence": [0,1,1,0,0,0],       // who..what 증거(0/1)
    "ex_flag": 0,
    "con_flag": 0
  }
}
~~~

---

### 노드2: `02_update_metrics.py` — 메트릭 갱신

**입력**: `parsed, metrics`

**출력**
~~~json
{
  "metrics_updated": { ... },          // w/ex/con/utter_freq 증분 반영
  "missing_cells": [
    { "material_id":[2,3,2], "type":"why" },
    { "material_id":[1,1,1], "type":"where" },
    { "material_id":[2,3,2], "type":"ex" }
  ]
}
~~~

- `material_hits` 내 **모든 소재**의 `utter_freq += 1`  
- `w_evidence[i]==1` → `w[i] = 1` (상한 유지)  
- `ex_flag==1` → `ex=1`, `con_flag==1` → `con=1`  
- `missing_cells`는 **아직 0인 타입들만** 반환 (`who..what` + `ex` + `con`)

---

### 노드3: `03_generate_candidates.py` — TF=false에 대한 질문 생성

**입력**: `missing_cells, parsed.keywords, question_pool`

**출력**
~~~json
{
  "pool_delta": [
    {
      "id":"q-48b8",
      "material_id":[2,3,2],
      "keywords":["적금","첫직장",null],
      "type":"when",
      "text":"..."
    },
    {
      "id":"q-48b9",
      "material_id":[1,1,1],
      "keywords":["어머니","초등학교",null],
      "type":"where",
      "text":"..."
    }
  ]
}
~~~

- (material_id, type) 기준 **중복 회피**  
- 키워드는 최대 3개, 없으면 `null` padding  
- 문장 생성은 템플릿/LLM 병행

---

### 노드4: `04_select_questions.py` — 질문 선택 알고리즘

**입력**: `metrics_updated, question_pool + pool_delta, theme, engine_state`

**출력**
~~~json
{
  "next_question": {
    "id":"q-48b8",
    "material_id":[2,3,2],
    "type":"when",
    "text":"..."
  },
  "pool_to_save": [ ... ],
  "metrics_to_save": { ... }
}
~~~

> **선택 로직 예시**  
> - 1순위: 직전 소재 유지(단, `last_material_streak ≥ 3`이면 전환)  
> - 2순위: `chunk_weight` 내림차순(같은 덩어리 먼저)  
> - 3순위: 해당 덩어리 내 `sum(w)`가 작은 소재 우선  
> - 4순위: 탐색(ε-greedy) 적용 가능

---

## Prompt Flow — Chat DAG (스케치)

~~~yaml
# flows/interviews/chat/interview_chat_v2/flow.dag.yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
inputs:
  sessionId: {type: string}
  question:  {type: object}   # {id, material_id, type}
  answerText:{type: string}
  metrics:   {type: object}
  question_pool: {type: array}

outputs:
  next_question:   {type: object, reference: ${select.output.next_question}}
  pool_to_save:    {type: array,  reference: ${select.output.pool_to_save}}
  metrics_to_save: {type: object, reference: ${select.output.metrics_to_save}}

nodes:
- name: parse
  type: python
  source: {type: code, path: nodes/01_parse_answer.py}
  inputs:
    question:   ${inputs.question}
    answerText: ${inputs.answerText}
    metrics:    ${inputs.metrics}

- name: update
  type: python
  source: {type: code, path: nodes/02_update_metrics.py}
  inputs:
    parsed:  ${parse.output.parsed}
    metrics: ${inputs.metrics}

- name: gen
  type: python
  source: {type: code, path: nodes/03_generate_candidates.py}
  inputs:
    missing_cells: ${update.output.missing_cells}
    keywords:      ${parse.output.parsed.keywords}
    question_pool: ${inputs.question_pool}

- name: select
  type: python
  source: {type: code, path: nodes/04_select_questions.py}
  inputs:
    metrics_updated: ${update.output.metrics_updated}
    pool_delta:      ${gen.output.pool_delta}
    theme:           ${inputs.metrics.theme}
    engine_state:    ${inputs.metrics.engine_state}
    question_pool:   ${inputs.question_pool}
~~~

---

## Prompt Flow — Standard Worker (질문 1문장 생성)

> **LLM 노드만 사용**(코드 임포트 없음; **Connection**이 키/엔드포인트 처리)

~~~yaml
# flows/interviews/standard/generate_interview_question_v2/flow.dag.yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json

inputs:
  type:        { type: string, default: why }          # who|why|when|how|where|what|ex|con
  material:    { type: string, default: 부모 }
  keywords:
    type: array
    default: [어머니, 초등학교, 도시락]
  tone:        { type: string, default: 따뜻하고 존중하는 어조 }
  max_len:     { type: int,    default: 120 }
  model:       { type: string, default: gpt-4o-mini }
  temperature: { type: number, default: 0.3 }

outputs:
  text:            { type: string, reference: ${guard.output.text} }
  policyVersion:   { type: string, reference: ${guard.output.policyVersion} }
  templateVersion: { type: string, reference: ${guard.output.templateVersion} }

nodes:
- name: llm
  type: llm
  source:
    type: prompt
    path: prompts/ask_question_v2.jinja2
  inputs:
    material:    ${inputs.material}
    type:        ${inputs.type}
    keywords:    ${inputs.keywords}
    tone:        ${inputs.tone}
    max_len:     ${inputs.max_len}
    model:       ${inputs.model}
    temperature: ${inputs.temperature}
    max_tokens:  128
    top_p:       1
  connection: ${connections.open_ai_connection}
  api: chat

- name: guard
  type: python
  source:
    type: code
    path: nodes/03_guard.py
  inputs:
    raw_text: ${llm.output}
    max_len:  ${inputs.max_len}
~~~

**프롬프트** (`prompts/ask_question_v2.jinja2`)

~~~jinja2
You are an interviewing assistant for an autobiography project.
Goal: Create ONE concise follow-up question in Korean.

Material: {{ material }}
Type: {{ type }}  {# who|why|when|how|where|what|ex|con #}
{% if keywords %}Keywords: {{ keywords | reject('equalto', None) | list | join(', ') }}{% endif %}

Constraints:
- Warm, respectful, ≤ {{ max_len }} chars.
- No double questions.
- If type == "ex": ask for a concrete example.
- If type == "con": ask for more concrete details.

Return only the question sentence (Korean).

Examples (DO NOT COPY, JUST REFERENCE STYLE):
- ex: "{{ material }}에 대한 구체적인 사례를 한 가지 들려주실 수 있을까요?"
- con: "{{ material }}과(와) 관련된 내용을 더 구체적으로 설명해 주실 수 있을까요?"
- who: "{{ material }}와 관련된 사람은 누구였나요?"
- why: "{{ material }}에 대해 그렇게 생각하게 된 이유는 무엇인가요?"
- when: "{{ material }}와 관련된 중요한 시기는 언제였나요?"
- how: "{{ material }}을/를 어떻게 경험하게 되었나요?"
- where: "{{ material }} 사건이 일어난 장소는 어디였나요?"
- what: "{{ material }}에 대해 더 자세히 설명해 주시겠어요?"
~~~

**가드 노드** (`nodes/03_guard.py`)

~~~py
from promptflow.core import tool

POLICY_VERSION = "v2.0.0"
TEMPLATE_VERSION = "ask_question_v2.0"

def _normalize(text: str, max_len: int) -> str:
    s = " ".join((text or "").split())
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    if not s.endswith(("?", "요.", "요?")):
        s = s.rstrip(".") + "?"
    return s

@tool
def guard_and_format(raw_text: str, max_len: int = 120):
    s = _normalize(raw_text, max_len)
    return {
        "text": s,
        "policyVersion": POLICY_VERSION,
        "templateVersion": TEMPLATE_VERSION
    }
~~~

---

## Serve — Router 예시 (FastAPI)

> 표준 워커는 **Connection**으로 LLM을 호출하므로, 서버 코드에서 키를 다룰 필요 없음.

~~~py
# serve/interviews/interview_question_v2/router.py
from fastapi import APIRouter, HTTPException, Depends
from promptflow.core import Flow
from starlette.requests import Request
from pydantic_core import ValidationError
from pathlib import Path

from auth import AuthRequired, get_current_user
from interviews.generate_interview_question.dto.request import InterviewQuestionGenerateRequestDto
from interviews.generate_interview_question.dto.response import InterviewQuestionGenerateResponseDto
from logs import get_logger

logger = get_logger()
router = APIRouter()

# Flow는 모듈 로드시 1번만 로드(성능↑)
try:
    FLOW_PATH = (
        Path(__file__).resolve().parents[3]
        / "flows" / "interviews" / "standard"
        / "generate_interview_question_v2" / "flow.dag.yaml"
    )
    FLOW = Flow.load(str(FLOW_PATH))
except Exception as e:
    logger.error(f"Failed to load flow at startup: {e}")
    FLOW = None

@router.post(
    "/api/v2/interviews/interview-questions",
    dependencies=[Depends(AuthRequired())],
    response_model=InterviewQuestionGenerateResponseDto,
    summary="인터뷰 질문 생성 v2",
    description="질문 생성 알고리즘(표준 워커 v2)으로 한 문장의 인터뷰 질문을 생성합니다.",
    tags=["인터뷰 (Interview)"],
)
async def generate_interview_questions(
    request: Request,
    requestDto: InterviewQuestionGenerateRequestDto,
    current_user=Depends(get_current_user),
):
    if FLOW is None:
        raise HTTPException(status_code=500, detail="Question generator flow is not loaded.")

    if not requestDto.material.strip():
        raise HTTPException(status_code=400, detail="material is required.")
    if requestDto.max_len <= 0 or requestDto.max_len > 400:
        raise HTTPException(status_code=400, detail="max_len must be 1~400.")

    try:
        outputs = FLOW(
            type=requestDto.type,
            material=requestDto.material,
            keywords=requestDto.keywords,
            tone=requestDto.tone,
            max_len=requestDto.max_len,
            model=requestDto.model,
            temperature=requestDto.temperature,
        )
        if not isinstance(outputs, dict) or "text" not in outputs:
            logger.error(f"Unexpected flow output: {outputs}")
            raise HTTPException(status_code=500, detail="Invalid output from question generator.")
        return InterviewQuestionGenerateResponseDto(**outputs)

    except ValidationError as e:
        logger.error(f"Response validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error while generating interview question")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
~~~

**요청/응답 DTO (예시)**

~~~py
# serve/interviews/interview_question_v2/dto/request.py
from pydantic import BaseModel
from typing import Literal, List

class InterviewQuestionGenerateRequestDto(BaseModel):
    type: Literal["who","why","when","how","where","what","ex","con"]
    material: str
    keywords: List[str] = []
    tone: str = "따뜻하고 존중하는 어조"
    max_len: int = 120
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
~~~

~~~py
# serve/interviews/interview_question_v2/dto/response.py
from pydantic import BaseModel

class InterviewQuestionGenerateResponseDto(BaseModel):
    text: str
    policyVersion: str
    templateVersion: str
~~~

---

## 백엔드 ↔ AI 서버 통신 (턴 API)

**요청**

~~~json
{
  "sessionId": "sess-001",
  "question": { "id":"q-47ab", "material_id":[1,1,1], "type":"why" },
  "answerText": "초등학교 때 어머니가...",
  "metrics": { ... },        // 백엔드 저장본(상단 Metrics)
  "question_pool": [ ... ]   // 백엔드 저장본(queued/asked/dropped 포함)
}
~~~

**응답**

~~~json
{
  "next_question": { "id":"q-48b8", "material_id":[2,3,2], "type":"when", "text":"..." },
  "pool_to_save": [ ... ],     // 새로 생성된 후보들(queued)
  "metrics_to_save": { ... }   // 갱신본(메트릭 + engine_state 포함 가능)
}
~~~

> 백엔드는 `pool_to_save`를 머지/중복제거 후 저장하고, `metrics_to_save`로 메트릭/엔진상태를 갱신.  
> 선택된 `question.id`는 **asked**로 마킹.

---

## Test Run — 샘플 입력

~~~json
{
  "sessionId": "sess-001",
  "question": {
    "id": "q-47ab",
    "material_id": [1,1,1],
    "type": "why",
    "text": "부모님께 감사하게 된 계기는 무엇인가요?"
  },
  "answerText": "초등학교 때 어머니가 매일 새벽에 도시락을 싸주셨어요. 그 덕분에 책임감과 가족의 사랑을 배웠어요.",
  "metrics": {
    "theme": "family",
    "categories": {
      "1": {
        "category_num": 1,
        "category_name": "부모",
        "chunks": {
          "1": {
            "chunk_num": 1,
            "chunk_name": "성격",
            "materials": {
              "1": {
                "material_num": 1,
                "material_name": "부모",
                "w": [1,1,0,1,0,1],
                "ex": 0,
                "con": 0,
                "material_count": 0,
                "utter_freq": 3
              }
            }
          }
        },
        "chunk_weight": { "1": 10 }
      }
    },
    "engine_state": {
      "last_material_id": [1,1,1],
      "last_material_streak": 1,
      "epsilon": 0.1
    },
    "asked_total": 4,
    "policyVersion": "v2.0.0"
  },
  "question_pool": []
}
~~~

---

## 체크리스트

- **Prompt Flow Connection**: `open_ai_connection` 생성 후, standard LLM 노드에 `connection: ${connections.open_ai_connection}` 지정
- **경로 구분자**: Windows라도 `flow.dag.yaml`에서는 **항상 `/`** 사용
- **Python 인터프리터**: VS Code에서 `.venv` 선택 (필요 시 `promptflow.pythonPath` 설정)
- **의존**: standard 워커는 LLM 노드만 사용 → 별도 `openai` SDK 불필요
- **성능**: `Flow.load()`는 앱 시작 시 1회만 수행(모듈 레벨 캐시)
- **버전 운영**: `chat/interview_chat_v1|v2`, `standard/generate_interview_question_v1|v2` 공존 가능

---

## 버전/롤백 전략

- **버저닝 폴더**:  
  - `flows/interviews/chat/interview_chat_v2/`  
  - `flows/interviews/standard/generate_interview_question_v2/`
- **API 분리**: `/api/v2/...`로 노출, 내부에서 standard v2 ↔ v1 스위칭 가능
- **롤백**: 질문 품질 이슈 발생 시 standard만 v1으로 즉시 롤백(오케스트레이션 수정 無)

---

## 왜 chat / standard 를 분리하나?

- **관심사 분리**: 세션 상태·우선순위·정책(=chat) vs. 순수 텍스트 생성(=standard)  
- **재사용성**: standard 워커는 chat/evaluation/배치/서빙 등 어디서든 호출  
- **테스트/AB**: 입력/출력이 고정되어 실험·정량화 용이  
- **릴리즈 안정성**: standard 교체만으로 품질 롤백/업그레이드  
- **비용/지연 관리**: LLM 호출 위치/횟수 일원화 (캐시/레이트리밋)


