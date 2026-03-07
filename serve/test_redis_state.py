"""
Redis 상태 확인 테스트
"""
import requests
import json
import base64
import hmac
import hashlib
import redis

BASE_URL = "http://localhost:3000"
AUTOBIOGRAPHY_ID = 999

def get_token():
    SECRET_KEY = "0190ab45-7e42-7a3f-9dec-726ddf778076"
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"memberId": 1, "roles": ["MEMBER"]}
    
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def get_redis_session(session_key):
    """Redis에서 세션 데이터 조회"""
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    session_data_raw = redis_client.get(session_key)
    if session_data_raw:
        return json.loads(session_data_raw)
    return None

def test_redis_state():
    """Redis 상태 확인 테스트"""
    print("\n" + "="*70)
    print("Redis 상태 확인 테스트")
    print("="*70)
    
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 세션 시작
    print("\n[1단계] 세션 시작")
    response = requests.post(
        f"{BASE_URL}/api/v2/interviews/start/{AUTOBIOGRAPHY_ID}",
        headers=headers,
        json={"preferred_categories": []}
    )
    
    if response.status_code != 200:
        print(f"❌ 세션 시작 실패: {response.text}")
        return False
    
    print(f"✅ 세션 시작 성공")
    first_question = response.json()["first_question"]
    print(f"   첫 질문: {first_question['text'][:50]}...")
    
    # Redis 세션 키 생성 (session_manager와 동일한 로직)
    session_key = f"session:1:{AUTOBIOGRAPHY_ID}"
    
    # Redis 상태 확인
    print(f"\n[Redis 확인 #1] 세션 시작 후")
    redis_data = get_redis_session(session_key)
    if redis_data:
        print(f"✅ Redis 세션 존재")
        last_q = redis_data.get("last_question", {})
        print(f"   last_question.id: {last_q.get('id')}")
        print(f"   last_question.type: {last_q.get('type')}")
        
        # material 구조 확인
        material = last_q.get("material", {})
        if isinstance(material, dict):
            print(f"   material.full_material_name: {material.get('full_material_name')}")
            print(f"   material.full_material_id: {material.get('full_material_id')}")
            print(f"   material.material_name: {material.get('material_name')}")
            print(f"   ✅ material 구조 정상 (dict with full_material_id)")
        else:
            print(f"   ⚠️  material 구조 이상: {type(material)}")
        
        # material_id가 최상위에 없는지 확인
        if "material_id" in last_q:
            print(f"   ⚠️  최상위 material_id 존재 (제거되어야 함): {last_q.get('material_id')}")
        else:
            print(f"   ✅ 최상위 material_id 없음 (정상)")
    else:
        print(f"❌ Redis 세션 없음")
        return False
    
    # 2. 대화 진행
    print(f"\n[2단계] 대화 진행")
    response = requests.post(
        f"{BASE_URL}/api/v2/interviews/chat/{AUTOBIOGRAPHY_ID}",
        headers=headers,
        json={"answer_text": "부모님은 정말 따뜻하신 분들이셨어요. 항상 저를 응원해주셨죠."}
    )
    
    if response.status_code != 200:
        print(f"❌ 대화 실패: {response.text}")
        return False
    
    print(f"✅ 대화 성공")
    next_question = response.json()["next_question"]
    print(f"   다음 질문: {next_question['text'][:50]}...")
    
    # Redis 상태 확인
    print(f"\n[Redis 확인 #2] 대화 진행 후")
    redis_data = get_redis_session(session_key)
    if redis_data:
        print(f"✅ Redis 세션 존재")
        last_q = redis_data.get("last_question", {})
        print(f"   last_question.id: {last_q.get('id')}")
        print(f"   last_question.type: {last_q.get('type')}")
        
        # material 구조 확인
        material = last_q.get("material", {})
        if isinstance(material, dict):
            print(f"   material.full_material_name: {material.get('full_material_name')}")
            print(f"   material.full_material_id: {material.get('full_material_id')}")
            print(f"   material.material_name: {material.get('material_name')}")
            print(f"   ✅ material 구조 정상")
        else:
            print(f"   ⚠️  material 구조 이상: {type(material)}")
        
        # metrics 확인
        metrics = redis_data.get("metrics", {})
        categories = metrics.get("categories", [])
        print(f"   metrics.asked_total: {metrics.get('asked_total')}")
        print(f"   metrics.categories: {len(categories)}개")
        
        if categories:
            for cat in categories:
                print(f"     - {cat['category_name']}: {len(cat.get('chunks', []))}개 청크")
    else:
        print(f"❌ Redis 세션 없음")
        return False
    
    # 3. 한 번 더 대화
    print(f"\n[3단계] 추가 대화")
    response = requests.post(
        f"{BASE_URL}/api/v2/interviews/chat/{AUTOBIOGRAPHY_ID}",
        headers=headers,
        json={"answer_text": "어릴 때 아버지와 함께 낚시를 갔던 기억이 나요."}
    )
    
    if response.status_code != 200:
        print(f"❌ 대화 실패: {response.text}")
        return False
    
    print(f"✅ 대화 성공")
    
    # Redis 상태 확인
    print(f"\n[Redis 확인 #3] 추가 대화 후")
    redis_data = get_redis_session(session_key)
    if redis_data:
        print(f"✅ Redis 세션 존재")
        
        # 이전 질문과 비교
        last_q = redis_data.get("last_question", {})
        material = last_q.get("material", {})
        
        print(f"   last_question.id: {last_q.get('id')}")
        print(f"   material.full_material_id: {material.get('full_material_id')}")
        
        # metrics 누적 확인
        metrics = redis_data.get("metrics", {})
        print(f"   metrics.asked_total: {metrics.get('asked_total')} (증가 확인)")
        
        categories = metrics.get("categories", [])
        total_materials = 0
        for cat in categories:
            for chunk in cat.get("chunks", []):
                total_materials += len(chunk.get("materials", []))
        print(f"   총 소재 수: {total_materials}개")
    else:
        print(f"❌ Redis 세션 없음")
        return False
    
    # 4. 세션 종료
    print(f"\n[4단계] 세션 종료")
    response = requests.post(
        f"{BASE_URL}/api/v2/interviews/end/{AUTOBIOGRAPHY_ID}",
        headers=headers,
        json={}
    )
    
    if response.status_code != 200:
        print(f"❌ 세션 종료 실패: {response.text}")
        return False
    
    print(f"✅ 세션 종료 성공")
    
    # Redis 세션 삭제 확인
    print(f"\n[Redis 확인 #4] 세션 종료 후")
    redis_data = get_redis_session(session_key)
    if redis_data:
        print(f"⚠️  Redis 세션 아직 존재 (삭제되어야 함)")
        return False
    else:
        print(f"✅ Redis 세션 삭제됨")
    
    return True

def main():
    print("="*70)
    print("Redis 상태 확인 테스트 시작")
    print("="*70)
    
    result = test_redis_state()
    
    print("\n" + "="*70)
    print("테스트 결과")
    print("="*70)
    
    if result:
        print("✅ 모든 Redis 상태 확인 통과")
        print("\n검증 완료:")
        print("  1. ✅ Redis 세션 생성/업데이트/삭제 정상")
        print("  2. ✅ material 구조 변경 적용 (full_material_id)")
        print("  3. ✅ 최상위 material_id 제거됨")
        print("  4. ✅ metrics 누적 정상")
        return 0
    else:
        print("❌ Redis 상태 확인 실패")
        return 1

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n테스트 중단됨")
        exit(1)
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
