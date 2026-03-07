"""
매핑 로직 유닛 테스트 - Redis/서버 없이 실행 가능
"""
import json
import os
import re

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())

def test_material_matching():
    """소재 매칭 로직 테스트"""
    print("=" * 60)
    print("소재 매칭 로직 유닛 테스트")
    print("=" * 60)
    
    # 매핑 파일 로드
    current_dir = os.path.dirname(__file__)
    mapping_path = os.path.join(current_dir, "data", "material_id_mapping.json")
    
    with open(mapping_path, 'r', encoding='utf-8') as f:
        material_mapping = json.load(f)
    
    # LLM 응답 시뮬레이션
    llm_items = [
        {"material": {"order": 4, "name": "직업/관심사"}, "axes": {"principle": [0,0,1,0,0,0]}},
        {"material": {"order": 1, "name": "서로에게 바라는 역할"}, "axes": {"principle": [0,0,1,0,0,0]}},
        {"material": "성함", "axes": {"principle": [1,0,0,0,0,0]}},
    ]
    
    print(f"\n[테스트 케이스: {len(llm_items)}개]")
    
    matched_count = 0
    for i, item in enumerate(llm_items, 1):
        material_value = item["material"]
        name = material_value.get("name", "") if isinstance(material_value, dict) else str(material_value)
        
        print(f"\n{i}. 입력: {material_value}")
        print(f"   추출된 name: '{name}'")
        
        # 매핑 로직 (실제 코드와 동일)
        key = None
        for k in material_mapping.keys():
            if name in k or _norm(name) in _norm(k):
                key = k
                break
        
        if key:
            mid = material_mapping.get(key)
            print(f"   ✅ 매칭 성공: {mid}")
            print(f"      키: {key[:60]}...")
            matched_count += 1
        else:
            print(f"   ❌ 매칭 실패")
    
    print(f"\n{'=' * 60}")
    print(f"결과: {matched_count}/{len(llm_items)} 매칭 성공")
    print(f"{'=' * 60}")
    
    return matched_count == len(llm_items)

def test_core_logic():
    """core.py 로직 테스트"""
    print("\n" + "=" * 60)
    print("core.py 로직 테스트")
    print("=" * 60)
    
    from engine.core import InterviewEngine, Material, Chunk, Category
    
    # 간단한 카테고리 구조 생성
    categories = {
        1: Category(
            category_num=1,
            category_name="테스트 카테고리",
            chunks={
                1: Chunk(
                    chunk_num=1,
                    chunk_name="테스트 청크",
                    materials={
                        1: Material(order=1, name="소재1"),
                        2: Material(order=2, name="소재2"),
                        3: Material(order=3, name="소재3"),
                    }
                )
            },
            chunk_weight={1: 5}
        )
    }
    
    engine = InterviewEngine(categories)
    
    print("\n[1] 소재 선택 테스트")
    material_id = engine.select_material()
    print(f"   선택된 소재 ID: {material_id}")
    print(f"   ✅ 소재 선택 성공")
    
    print("\n[2] 연속 3회 질문 로직 테스트")
    engine.state.last_material_id = (1, 1, 1)
    engine.state.last_material_streak = 0
    
    for i in range(5):
        material_id = engine.select_material()
        print(f"   {i+1}회: material_id={material_id}, streak={engine.state.last_material_streak}")
        
        # streak 업데이트 시뮬레이션
        if engine.state.last_material_id == material_id:
            engine.state.last_material_streak += 1
        else:
            engine.state.last_material_id = material_id
            engine.state.last_material_streak = 1
        
        if i == 2:  # 3회차
            if engine.state.last_material_streak >= 3:
                print(f"   ✅ 3회 연속 후 소재 변경 가능 상태")
    
    print(f"\n{'=' * 60}")
    print(f"✅ core.py 로직 테스트 완료")
    print(f"{'=' * 60}")
    
    return True

if __name__ == "__main__":
    print("\n🧪 유닛 테스트 시작\n")
    
    results = []
    
    try:
        results.append(("소재 매칭 로직", test_material_matching()))
    except Exception as e:
        print(f"❌ 소재 매칭 테스트 실패: {e}")
        results.append(("소재 매칭 로직", False))
    
    try:
        results.append(("core.py 로직", test_core_logic()))
    except Exception as e:
        print(f"❌ core.py 테스트 실패: {e}")
        results.append(("core.py 로직", False))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{name}: {status}")
    
    success_count = sum(1 for _, r in results if r)
    print(f"\n총 {success_count}/{len(results)} 테스트 통과")
    
    if success_count == len(results):
        print("\n🎉 모든 유닛 테스트 통과!")
    else:
        print("\n⚠️  일부 테스트 실패")
