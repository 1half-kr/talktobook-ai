import json
import os
import re

def _norm(s: str) -> str:
    """공백 제거 + trim 후 비교용 문자열로 정규화"""
    return re.sub(r"\s+", "", (s or "").strip())

# 파일 경로
current_dir = os.path.dirname(__file__)
mapping_path = os.path.join(current_dir, "data", "material_id_mapping.json")

# 매핑 파일 로드
with open(mapping_path, 'r', encoding='utf-8') as f:
    material_mapping = json.load(f)
    norm_index = {_norm(k): k for k in material_mapping.keys()}

# 테스트 케이스
test_cases = [
    # dict 형태 (LLM이 반환하는 형식)
    {"material": {"order": 4, "name": "직업/관심사"}, "axes": {"principle": [0,0,1,0,0,0]}},
    {"material": {"order": 1, "name": "서로에게 바라는 역할"}, "axes": {"principle": [0,0,1,0,0,0]}},
    {"material": {"order": 2, "name": "친밀감의 농도"}, "axes": {"principle": [0,0,1,0,0,0]}},
    # 문자열 형태
    {"material": "직업/관심사", "axes": {"principle": [0,0,1,0,0,0]}},
    {"material": "파트너(배우자) 기본정보 직업/관심사", "axes": {"principle": [0,0,1,0,0,0]}},
]

print("=" * 60)
print("매핑 테스트 시작 (수정된 로직)")
print("=" * 60)

for idx, item in enumerate(test_cases, 1):
    print(f"\n[테스트 {idx}]")
    material_value = item["material"]
    print(f"입력: {material_value}")
    
    # dict 형태면 name만 추출
    name = material_value.get("name", "") if isinstance(material_value, dict) else str(material_value)
    print(f"  → 추출된 name: '{name}'")
    
    if not name:
        print("  ✗ name이 비어있음")
        continue
    
    # 매핑 파일에서 찾기 (여러 패턴 시도)
    key = None
    for k in material_mapping.keys():
        if name in k or _norm(name) in _norm(k):
            key = k
            break
    
    if key:
        mid = material_mapping.get(key)
        print(f"  ✓ 매핑 성공: '{key}' → {mid}")
    else:
        print(f"  ✗ 매핑 실패: '{name}'")
        similar = [k for k in material_mapping.keys() if name in k]
        if similar:
            print(f"    유사한 키: {similar[:3]}")

print("\n" + "=" * 60)
print("매핑 테스트 완료")
print("=" * 60)
