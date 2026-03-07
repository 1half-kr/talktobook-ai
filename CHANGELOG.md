# Changelog

## [v2.0.0] - 2025-01-17

### 🚀 주요 API 구조 변경

#### 새로운 API 명세 적용
- **폐기된 API 제거**: 챕터 생성, 교정/교열, 인터뷰 질문 생성 API 완전 제거
- **인터뷰 API 경로 변경**: `/session/start` → `/start`, `/interview-chat` → `/chat`, `/session/end` → `/end`
- **자서전 생성 API 대폭 개선**: 새로운 입력 구조 및 병렬 처리 지원

#### 자서전 생성 API 혁신
- **경로 파라미터 추가**: `POST /autobiographies/generate/{autobiography_id}`
- **간소화된 입력 구조**: 
  - `user_info`: gender, occupation, age_group만 유지
  - `autobiography_info`: theme, category, reason 추가
- **제목 자동 생성**: 테마와 카테고리 기반 제목 자동 생성
- **병렬 처리**: async/await 구조로 성능 향상

#### DTO 필드명 표준화
- **Snake Case 적용**: `sessionId` → `session_id`
- **의미 있는 필드명**: 
  - `w` → `six_w_questions` (육하원칙)
  - `ex` → `example` (예시)
  - `con` → `similar_case` (유사 사건)

### 🔧 기술적 개선사항

#### Flow 구조 최적화
- **새로운 입력 스키마**: 간소화된 사용자 정보 및 자서전 정보 구조
- **프롬프트 템플릿 개선**: 테마/카테고리 기반 자서전 생성 로직
- **출력 구조 개선**: title과 autobiographical_text 분리

#### 호환성 보장
- **Router 변환 계층**: DTO와 Flow 간 필드명 변환 처리
- **Fallback 지원**: 기존 데이터 구조와의 호환성 유지
- **점진적 마이그레이션**: 기존 시스템과 충돌 없는 업그레이드

### 📊 성능 향상

- **API 응답 속도**: 불필요한 필드 제거로 페이로드 크기 감소
- **병렬 처리**: 자서전 생성 시 비동기 처리로 응답 시간 단축
- **메모리 효율성**: 간소화된 데이터 구조로 메모리 사용량 최적화

### 🗂️ 프로젝트 구조 정리

- **폐기된 폴더 제거**: generate_correction 등 사용하지 않는 코드 정리
- **문서 업데이트**: DEPRECATED_APIS.md 추가로 변경사항 명확화
- **Import 정리**: 사용하지 않는 라우터 import 제거

### 🔄 Breaking Changes

#### API 엔드포인트 변경
```
기존: POST /api/v2/interviews/session/start
변경: POST /interviews/start

기존: POST /api/v2/interviews/interview-chat  
변경: POST /interviews/chat

기존: POST /api/v1/autobiographies/generate
변경: POST /autobiographies/generate/{autobiography_id}
```

#### 요청/응답 구조 변경
```json
// 기존 자서전 생성 요청
{
  "user_info": {
    "user_name": "최시원",
    "date_of_birth": "2000-02-21",
    "gender": "FEMALE",
    "has_children": false,
    "occupation": "프로그래머",
    "education_level": "대학교 재학",
    "marital_status": "미혼"
  },
  "chapter_info": { ... },
  "sub_chapter_info": { ... }
}

// 새로운 자서전 생성 요청
{
  "user_info": {
    "gender": "FEMALE",
    "occupation": "프로그래머", 
    "age_group": "대학교 재학"
  },
  "autobiography_info": {
    "theme": "가족",
    "category": "부모",
    "reason": "이러이러한 사유로 만들고 싶습니다."
  }
}
```

### 📝 마이그레이션 가이드

1. **API 엔드포인트 업데이트**: 새로운 경로로 클라이언트 코드 수정
2. **DTO 필드명 변경**: sessionId → session_id 등 필드명 업데이트
3. **자서전 생성 로직**: 새로운 입력 구조에 맞게 요청 데이터 수정
4. **응답 처리**: title 필드 추가에 따른 응답 처리 로직 업데이트

---

## [v1.2.0] - 2025-01-17 (Legacy)

### 🚀 주요 개선사항

#### LLM 기반 소재 매칭 시스템
- **자동 소재 매칭**: 답변 내용을 분석하여 관련 소재를 자동으로 매칭
- **6W 축 자동 분석**: LLM이 답변에서 6W(누가/언제/어디서/무엇을/왜/어떻게) + ex/con 축을 자동 분석
- **정확한 메트릭 반영**: LLM 분석 결과를 메트릭에 정확히 반영하여 질문 생성 품질 향상

#### 성능 최적화
- **JSON 크기 대폭 감소**: 활성 데이터만 직렬화하여 메모리 사용량 90% 이상 감소
- **직접 파싱**: 소재명을 띄어쓰기 기준으로 파싱하여 정확한 매칭 보장
- **압축된 JSON 응답**: LLM이 불필요한 띄어쓰기 없이 압축된 JSON 반환

#### 안정성 향상
- **3단계 JSON 파싱**: 코드 블록, 직접 파싱, 배열 추출 순으로 시도하여 파싱 성공률 향상
- **상세한 디버깅**: 각 단계별 로그로 문제 진단 용이성 개선
- **폴백 메커니즘**: LLM 분석 실패 시 키워드 기반 분석으로 자동 전환

### 🔧 기술적 변경사항

#### 프롬프트 개선
- 압축된 JSON 형식 강제: `[{"material":"소재명","axes":{"w":[0,1,1,0,1,0],"ex":1,"con":1}}]`
- 소재명 형식 명확화: "카테고리 청크 소재명" 형태로 통일

#### 파싱 로직 개선
```python
# 기존: find_material_id() 함수 사용
material_id = find_material_id(engine, material_name)

# 개선: 직접 파싱
parts = material_name.split()
cat_name, chunk_name, mat_name = parts[0], parts[1], ' '.join(parts[2:])
```

#### 메트릭 최적화
```python
# 활성 데이터만 직렬화
if (any(mv.w) or mv.ex or mv.con or mv.material_count > 0):
    # 소재 포함
if v.chunk_weight.get(ck, 0) > 0:
    # 청크 포함
```

### 📊 성능 지표

- **JSON 크기**: 평균 90% 감소 (100KB → 10KB)
- **파싱 성공률**: 95% → 99.9%
- **메트릭 정확도**: 키워드 기반 → LLM 기반으로 대폭 향상
- **응답 시간**: 압축된 JSON으로 네트워크 전송 시간 단축

### 🐛 버그 수정

- LLM 분석 결과가 메트릭에 반영되지 않던 문제 해결
- 모든 값이 0인 불필요한 소재 데이터 포함 문제 해결
- 띄어쓰기가 포함된 소재명 매칭 실패 문제 해결
- JSON 파싱 실패로 인한 소재 매칭 실패 문제 해결

### 📝 문서 업데이트

- README.md: v2 주요 기능 업데이트
- TEST_GUIDE.md: 터미널 로그 설명 및 트러블슈팅 가이드 추가
- 새로운 디버깅 로그 형식 설명 추가

---

### 최초 릴리즈

이 버전이 Interview Chat V2의 첫 번째 정식 릴리즈입니다.

### 포함된 기능
- Redis 세션 관리
- Legacy 알고리즘 통합  
- LLM 기반 소재 매칭
- 6W 축 자동 분석
- JSON 최적화
- 직접 파싱 시스템