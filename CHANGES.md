# Interview Chat V2 - Material ID 기반 개선

## 변경 사항 요약

### 1. Material ID 기반 구조로 전환
- **이전**: material name 문자열 기반
- **현재**: material_id_mapping.json 기반 [category_order, chunk_order, material_order] 배열 사용

### 2. 주요 변경 파일

#### 2.1 Flow 레벨 (`ai/flows/interviews/chat/interview_chat_v2/`)
- **`__init__.py`**:
  - `_build_materials_list()` → `_build_materials_list_from_mapping()`: mapping에서 직접 리스트 생성
  - material_id 기반 소재 매칭 로직으로 변경
  - full_material_name 역검색 로직 추가
  - next_question의 material 필드를 dict 형태로 변경:
    ```json
    {
      "full_material_name": "카테고리 청크 {'order': X, 'name': '소재명'}",
      "material_name": "소재명",
      "material_order": X
    }
    ```

#### 2.2 Prompt 레벨 (`ai/flows/interviews/standard/map_answer_to_materials/`)
- **`map_materials.jinja2`**:
  - LLM이 material을 [category_order, chunk_order, material_order] 배열로 반환하도록 프롬프트 수정
  - materials_list의 각 항목에서 order 정보를 파싱하도록 지시

#### 2.3 Generator 레벨 (`ai/flows/interviews/chat/interview_chat_v2/engine/`)
- **`generators.py`**:
  - 첫 질문 생성 시에도 material을 dict 형태로 반환

#### 2.4 API 레벨 (`ai/serve/interviews/interview_chat_v2/`)
- **`dto/__init__.py`**:
  - Response DTO 예제를 새로운 material 구조로 업데이트

### 3. 데이터 구조

#### material_id_mapping.json 구조
```json
{
  "카테고리명 청크명 {'order': X, 'name': '소재명'}": [category_order, chunk_order, material_order]
}
```

예시:
```json
{
  "생애주기 청소년기(13-19) {'order': 1, 'name': '학교 생활'}": [14, 2, 1]
}
```

#### API Response 구조
```json
{
  "next_question": {
    "id": "q-abc123",
    "material": {
      "full_material_name": "생애주기 청소년기(13-19) {'order': 1, 'name': '학교 생활'}",
      "material_name": "학교 생활",
      "material_order": 1
    },
    "material_id": [14, 2, 1],
    "type": "w1",
    "text": "학교 생활에 대해 더 자세히 이야기해 주세요."
  },
  "last_answer_materials_id": [[14, 2, 1], [14, 2, 3]]
}
```

### 4. 로직 흐름

1. **질문 생성 시**:
   - Engine이 material_id 선택 → [cat, chunk, mat]
   - material_id로 material_mapping에서 full_material_name 역검색
   - material dict 구성: {full_material_name, material_name, material_order}

2. **답변 분석 시**:
   - LLM이 답변에서 소재 추출 → material_id 배열 반환
   - material_id로 Engine 업데이트
   - material_id로 full_material_name 역검색하여 매칭 확인

### 5. Redis 데이터 구조
- **변경 없음**: 기존 Redis 세션 구조 유지
- last_question에 새로운 material dict 구조 저장

### 6. 하위 호환성
- **주의**: API response 구조가 변경되었으므로 클라이언트 업데이트 필요
- material 필드가 string → dict로 변경

### 7. 테스트 방법

```bash
# Flow 테스트
cd ai/flows/interviews/chat/interview_chat_v2
# VSCode에서 flow.dag.yaml 열고 Test Run 실행

# API 테스트
cd ai/serve
python -m uvicorn main:app --env-file .env.development --port 3000
# http://localhost:3000/docs 에서 Swagger UI로 테스트
```

### 8. 주의사항

1. **LLM 프롬프트 변경**: map_materials.jinja2가 material_id 배열을 반환하도록 변경됨
2. **클라이언트 업데이트 필요**: material 필드 구조 변경
3. **material_id_mapping.json 필수**: 해당 파일이 없으면 동작하지 않음

### 9. 향후 개선 사항

- [ ] LLM이 material_id를 정확히 추출하는지 검증 로직 추가
- [ ] material_id_mapping.json 자동 생성 스크립트 개선
- [ ] 에러 핸들링 강화 (mapping 파일 없을 때 등)
