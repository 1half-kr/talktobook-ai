from promptflow.core import tool
from typing import Dict, List, Tuple
import json
import re
import sys
import os
import time
from uuid import uuid4
import logging

# Logger 설정
logger = logging.getLogger("interview_flow")

# engine 모듈 import 경로 추가
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from engine.core import InterviewEngine
from engine.utils import HINTS, EX_HINTS, CON_HINTS, hit_any, restore_categories_state
from engine.generators import generate_first_question, generate_question_llm, generate_material_gate_question

import redis

# ------------------ 공통 함수: serialize_categories ------------------
def serialize_categories(categories):
    result = []
    for cat in categories.values():
        active_chunks = {ck: cv for ck, cv in cat.chunks.items() if cat.chunk_weight.get(ck, 0) > 0}
        if not active_chunks:
            continue

        chunks = []
        for chunk in active_chunks.values():
            materials = [
                {"order": m.order, "name": m.name, "principle": m.principle,
                 "example": m.example, "similar_event": m.similar_event, "count": m.count}
                for m in chunk.materials.values()
                if any(m.principle) or m.example or m.similar_event or m.count > 0
            ]
            if materials:
                chunks.append({"chunk_num": chunk.chunk_num, "chunk_name": chunk.chunk_name, "materials": materials})

        if chunks:
            result.append({
                "category_num": cat.category_num,
                "category_name": cat.category_name,
                "chunks": chunks,
                "chunk_weight": {str(ck): w for ck, w in cat.chunk_weight.items() if w > 0}
            })
    return result

# ------------------ 공통 함수: publish_delta ------------------
def publish_delta(previous_categories, updated_metrics, user_id, autobiography_id):
    try:
        from datetime import datetime, timezone
        serve_dir = os.path.join(current_dir, '..', '..', '..', '..', 'serve')
        sys.path.insert(0, serve_dir)
        from stream import publish_categories_message
        from stream.dto import ChunksPayload, MaterialsPayload, CategoriesPayload
        
        now = datetime.now(timezone.utc)
        prev_cats = {c["category_num"]: c for c in previous_categories}
        
        logger.info(f"[DELTA] Starting delta calculation prev_categories={len(previous_categories)} curr_categories={len(updated_metrics['categories'])}")
        
        for curr_cat in updated_metrics["categories"]:
            cat_num = curr_cat["category_num"]
            prev_cat = prev_cats.get(cat_num, {})
            prev_chunks = {c["chunk_num"]: c for c in prev_cat.get("chunks", [])}
            chunks_deltas = []
            materials_deltas = []
            
            for curr_chunk in curr_cat["chunks"]:
                chunk_num = curr_chunk["chunk_num"]
                prev_chunk = prev_chunks.get(chunk_num, {})
                
                # chunk weight 변화
                prev_weight = prev_cat.get("chunk_weight", {}).get(str(chunk_num), 0)
                curr_weight = curr_cat["chunk_weight"].get(str(chunk_num), 0)
                
                if curr_weight > prev_weight:
                    chunks_deltas.append(ChunksPayload(
                        categoryId=cat_num, 
                        chunkOrder=chunk_num,
                        weight=curr_weight - prev_weight, 
                        timestamp=now
                    ))
                    logger.debug(f"[DELTA] Chunk weight changed cat={cat_num} chunk={chunk_num} delta={curr_weight - prev_weight}")
                
                # material 변화
                prev_materials = {m["order"]: m for m in prev_chunk.get("materials", [])}
                for curr_mat in curr_chunk["materials"]:
                    mat_order = curr_mat["order"]
                    prev_mat = prev_materials.get(mat_order, {})
                    
                    principle_delta = [curr_mat["principle"][i] - prev_mat.get("principle", [0,0,0,0,0,0])[i] for i in range(6)]
                    example_delta = curr_mat["example"] - prev_mat.get("example", 0)
                    similar_event_delta = curr_mat["similar_event"] - prev_mat.get("similar_event", 0)
                    count_delta = curr_mat["count"] - prev_mat.get("count", 0)
                    
                    if any(principle_delta) or example_delta or similar_event_delta or count_delta:
                        materials_deltas.append(MaterialsPayload(
                            chunkId=chunk_num, 
                            materialOrder=mat_order,
                            example=example_delta, 
                            similarEvent=similar_event_delta,
                            count=count_delta, 
                            principle=principle_delta, 
                            timestamp=now
                        ))
                        logger.debug(f"[DELTA] Material changed cat={cat_num} chunk={chunk_num} mat={mat_order} count_delta={count_delta}")
            
            if chunks_deltas or materials_deltas:
                # AI cat_num을 DB 매핑으로 변환
                theme_id, category_order = convert_cat_num_to_db_mapping(cat_num)
                
                final_payload = CategoriesPayload(
                    autobiographyId=int(autobiography_id),
                    userId=int(user_id),
                    themeId=theme_id,
                    categoryId=category_order,
                    chunks=chunks_deltas, 
                    materials=materials_deltas
                )
                
                logger.info(f"[DELTA] Publishing categories message cat_num={cat_num} theme_id={theme_id} category_id={category_order} chunks={len(chunks_deltas)} materials={len(materials_deltas)}")
                logger.info(f"[DELTA_DEBUG] chunks_deltas={chunks_deltas}")
                logger.info(f"[DELTA_DEBUG] materials_deltas={materials_deltas}")
                publish_categories_message(final_payload)
            else:
                logger.debug(f"[DELTA] No changes for category cat_num={cat_num}")
    except Exception as e:
        logger.warning(f"Delta 발행 실패: {e}", exc_info=True)

# 실제 함수 구현
def publish_delta_change(user_id, autobiography_id, theme_id, category_id, chunk_deltas=None, material_deltas=None):
    """실제 변화량을 CategoriesPayload로 전송"""
    try:
        
        # serve 디렉토리 경로 추가
        serve_dir = os.path.join(current_dir, '..', '..', '..', '..', 'serve')
        sys.path.insert(0, serve_dir)
        from stream import publish_categories_message
        from stream.dto import ChunksPayload, MaterialsPayload, CategoriesPayload
        
        # None 값 체크
        if user_id is None or autobiography_id is None:
            logger.debug("Skipping publish_delta_change due to None values")
            return
        
        # ChunksPayload 생성 (chunk_id를 chunkOrder로 매핑)
        chunks = []
        if chunk_deltas:
            for chunk_data in chunk_deltas:
                chunks.append(ChunksPayload(
                    categoryId=category_id,
                    chunkOrder=chunk_data.get('chunk_id', 0),  # chunk_id → chunkOrder
                    weight=chunk_data.get('weight_delta', 0),   # 변화량
                ))
        
        # MaterialsPayload 생성 (material_id를 materialOrder로 매핑)
        materials = []
        if material_deltas:
            for material_data in material_deltas:
                materials.append(MaterialsPayload(
                    chunkId=material_data.get('chunk_id', 0),     # 어느 chunk에 속하는지
                    materialOrder=material_data.get('material_id', 0), # material_id → materialOrder
                    example=material_data.get('example_delta', 0),     # 변화량
                    similarEvent=material_data.get('similar_event_delta', 0), # 변화량
                    count=material_data.get('count_delta', 0),         # 변화량
                    principle=material_data.get('principle_delta', [0,0,0,0,0,0]), # 변화량 배열
                ))
        
        # CategoriesPayload 생성 및 전송
        payload = CategoriesPayload(
            autobiographyId=int(autobiography_id),
            userId=int(user_id),
            themeId=theme_id,
            categoryId=category_id,
            chunks=chunks,
            materials=materials
        )
        
        
        publish_categories_message(payload)
        
    except Exception as e:
        logger.warning(f"Delta 발행 실패: {e}")
        pass


# ------------------------ 간단 헬퍼 ------------------------

def _norm(s: str) -> str:
    """공백 제거 + trim 후 비교용 문자열로 정규화"""
    return re.sub(r"\s+", "", (s or "").strip())


def _build_materials_list_from_mapping(mapping_path: str) -> dict:
    """material_id_mapping.json에서 {name: [cat, chunk, mat]} dict 반환"""
    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"material_id_mapping.json 로드 실패: {e}")
        return {}


def _call_llm_map_flow(flow_path: str, answer_text: str, materials_list: dict, current_material: str, current_material_id: List[int]) -> List[dict]:
    """LLM 플로우 호출"""
    if not os.path.exists(flow_path):
        return []

    try:
        from promptflow import load_flow
        flow = load_flow(flow_path)
        res = flow(answer_text=answer_text, materials_list=materials_list, current_material=current_material, current_material_id=current_material_id)
        items = res.get("analysis_result", [])
        
        
        # 문자열이면 JSON 파싱
        if isinstance(items, str):
            items = items.strip()
            # 마크다운 코드 블록 제거
            if items.startswith('```'):
                lines = items.split('\n')
                if lines[0].startswith('```'): lines = lines[1:]
                if lines and lines[-1].strip() == '```': lines = lines[:-1]
                items = '\n'.join(lines)
            items = json.loads(items)
        
        return items if isinstance(items, list) else []
    except Exception as e:
        logger.error(f"LLM 플로우 호출 실패: {e}")
        return []
    
# AI cat_num을 DB의 theme_id, category_order로 변환하는 함수
def convert_cat_num_to_db_mapping(cat_num):
    """AI의 cat_num을 DB의 (theme_order, category_order)로 변환"""
    # theme.json 기반 매핑
    mapping = {
        1: (1, 1),   # 부모 -> 가족사 전반
        2: (1, 2),   # 조부모 -> 가족사 전반
        3: (1, 3),   # 형제 -> 가족사 전반
        4: (1, 4),   # 자녀/육아 -> 가족사 전반
        5: (1, 5),   # 친척 -> 가족사 전반
        6: (1, 6),   # 가족 사건 -> 가족사 전반
        7: (4, 7),   # 주거지 -> 공간과 장소
        8: (5, 8),   # 성격 -> 나의 성격과 특성
        9: (2, 9),   # 결혼 -> 사랑과 결혼
        10: (2, 10), # 배우자 -> 사랑과 결혼
        11: (6, 11), # 친구 -> 관계
        12: (2, 12), # 연인 -> 사랑과 결혼
        13: (12, 13),# 반려동물 -> 반려동물과 함께한 삶
        14: (8, 14), # 생애주기 -> 시간의 흐름
        15: (7, 15), # 직장 -> 일과 성장
        16: (7, 16), # 진로 -> 일과 성장
        17: (7, 17), # 문제해결 -> 일과 성장
        18: (11, 18),# 취미 -> 취미와 여가
        19: (10, 19),# 금전 -> 경제생활
        20: (13, 20),# 철학 -> 가치관과 철학
        21: (14, 21),# 생활 -> 일상과 습관
    }
    
    return mapping.get(cat_num, (1, 1))  # 기본값

@tool
def interview_engine(sessionId: str, answer_text: str, user_id: int, autobiography_id: int) -> Dict:
    """인터뷰 엔진 - Redis에서 세션 로드하여 다음 질문 생성"""
    # Redis에서 세션 로드
    import redis
    import os
    import os
    
    # 환경변수에서 Redis 설정 읽기
    redis_host = os.getenv('REDIS_HOST')
    redis_port = int(os.getenv('REDIS_PORT'))
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
    session_key = f"session:{sessionId}"
    session_data_raw = redis_client.get(session_key)
    session_data = json.loads(session_data_raw) if session_data_raw and isinstance(session_data_raw, str) else None
    
    if session_data:
        logger.info(f"[SESSION] Loaded session data session_key={sessionId}")
    else:
        logger.info(f"[SESSION] No existing session data session_key={sessionId}")

    # 첫 질문 분기
    if not session_data or not session_data.get("last_question"):
        preferred_categories = session_data.get("metrics", {}).get("preferred_categories", []) if session_data else []
        logger.info(f"[FIRST_QUESTION] Generating first question preferred_categories={preferred_categories}")

        material_json_path = os.path.join(os.path.dirname(__file__), "data", "material.json")
        with open(material_json_path, 'r', encoding='utf-8') as f:
            material_data = json.load(f)


        categories = InterviewEngine.build_categories_from_category_json(material_data)
        engine = InterviewEngine(categories)
        
        # 테마 부스팅 적용
        if preferred_categories:
            engine.boost_theme(preferred_categories, initial_weight=10)
            
            # preferred_categories가 있으면 material gate 질문 생성
            material_id = engine.select_material()
            cat_num, chunk_num, mat_num = material_id
            material = engine._get_material(cat_num, chunk_num, mat_num)
            category = engine.categories[cat_num]
            chunk = category.chunks[chunk_num]
            full_material_name = f"{category.category_name} {chunk.chunk_name} {material.name}"
            
            gate_question_text = generate_material_gate_question(full_material_name)
            
            next_question = {
                "id": f"q-{uuid4().hex[:8]}",
                "material": {
                    "full_material_name": full_material_name,
                    "full_material_id": list(material_id),
                    "material_name": material.name,
                    "material_order": material.order
                },
                "type": "material_gate",
                "text": gate_question_text
            }
            
            updated_metrics = {
                "session_id": sessionId,
                "categories": serialize_categories(engine.categories),
                "engine_state": {
                    "last_material_id": list(engine.state.last_material_id) if engine.state.last_material_id else [],
                    "last_material_streak": engine.state.last_material_streak,
                    "epsilon": engine.state.epsilon
                },
                "asked_total": 1,
                "preferred_categories": preferred_categories,
                "policy_version": "v0.5.0"
            }
            
            session_update = {
                "metrics": updated_metrics,
                "last_question": next_question,
                "updated_at": time.time()
            }
            redis_client.setex(session_key, 3600, json.dumps(session_update))
            
            logger.info(f"🚧 [첫 질문 - Material Gate] {full_material_name}")
            return {"next_question": next_question, "last_answer_materials_id": []}
        else:
            # preferred_categories가 없으면 자유 질문
            metrics = {"preferred_categories": preferred_categories}
            result = generate_first_question(engine, metrics)
            if result.get("next_question") and "material_id" in result["next_question"]:
                material_id = result["next_question"].pop("material_id")
                result["next_question"]["material"]["full_material_id"] = material_id
            result["last_answer_materials_id"] = []
            return result

    # 이후 질문 생성 준비
    question = session_data.get("last_question", {})
    metrics = session_data.get("metrics", {})
    
    # material.json 로드 및 엔진 초기화
    material_json_path = os.path.join(os.path.dirname(__file__), "data", "material.json")
    try:
        with open(material_json_path, 'r', encoding='utf-8') as f:
            material_data = json.load(f)


        categories = InterviewEngine.build_categories_from_category_json(material_data)


        # 이전 메트릭이 있으면 상태 복원
        if metrics.get("categories"):
            restore_categories_state(categories, metrics["categories"])


        engine = InterviewEngine(categories)


        # 상태 복원
        engine_state = metrics.get("engine_state", {})
        engine.state.last_material_id = engine_state.get("last_material_id")
        engine.state.last_material_streak = engine_state.get("last_material_streak", 0)
        engine.theme_initialized = engine_state.get("theme_initialized", False)


    except Exception as e:
        logger.error(f"엔진 초기화 실패: {e}")
        return {"next_question": None, "last_answer_materials_id": []}

    # 답변 분석
    current_material = question.get("material", "") if question else ""
    # material_id는 material.full_material_id 또는 최상위 material_id에서 가져오기 (하위 호환)
    current_material_id = None
    if isinstance(current_material, dict):
        current_material_id = current_material.get("full_material_id")
    if not current_material_id:
        current_material_id = question.get("material_id") if question else None
    # material_id는 material.full_material_id 또는 최상위 material_id에서 가져오기 (하위 호환)
    current_material_id = None
    if isinstance(current_material, dict):
        current_material_id = current_material.get("full_material_id")
    if not current_material_id:
        current_material_id = question.get("material_id") if question else None
    is_first_question = not answer_text or not current_material
    
    # 현재 질문 소재의 full_material_name 찾기 (LLM에 전달용)
    current_material_full = ""
    if isinstance(current_material, dict):
        current_material_full = current_material.get("full_material_name", "")
    elif isinstance(current_material, str):
        current_material_full = current_material
    
    # full_material_name이 없으면 material_id로 역검색
    if not current_material_full and current_material_id and isinstance(current_material_id, list) and len(current_material_id) == 3:
        cat_num, chunk_num, mat_num = current_material_id
        temp_cat = engine.categories.get(cat_num)
        if temp_cat:
            temp_chunk = temp_cat.chunks.get(chunk_num)
            if temp_chunk:
                temp_mat = temp_chunk.materials.get(mat_num)
                if temp_mat:
                    current_material_full = f"{temp_cat.category_name} {temp_chunk.chunk_name} {temp_mat.name}"

    matched_materials: List[str] = []
    axes_analysis_by_material: Dict[str, dict] = {}
    mapped_ids: List[List[int]] = []

    
    # 현재 질문 소재의 full_material_name 찾기 (LLM에 전달용)
    current_material_full = ""
    if isinstance(current_material, dict):
        current_material_full = current_material.get("full_material_name", "")
    elif isinstance(current_material, str):
        current_material_full = current_material
    
    # full_material_name이 없으면 material_id로 역검색
    if not current_material_full and current_material_id and isinstance(current_material_id, list) and len(current_material_id) == 3:
        cat_num, chunk_num, mat_num = current_material_id
        temp_cat = engine.categories.get(cat_num)
        if temp_cat:
            temp_chunk = temp_cat.chunks.get(chunk_num)
            if temp_chunk:
                temp_mat = temp_chunk.materials.get(mat_num)
                if temp_mat:
                    current_material_full = f"{temp_cat.category_name} {temp_chunk.chunk_name} {temp_mat.name}"

    matched_materials: List[str] = []
    axes_analysis_by_material: Dict[str, dict] = {}
    mapped_ids: List[List[int]] = []

    if not is_first_question:
        # 6W 축 감지(휴리스틱, LLM 반환에 값 없을 때 보조로 사용)
        # 6W 축 감지(휴리스틱, LLM 반환에 값 없을 때 보조로 사용)
        axes_evidence = {k: hit_any(answer_text, HINTS[k]) for k in HINTS.keys()}
        ex_flag = 1 if hit_any(answer_text, EX_HINTS) else 0
        con_flag = 1 if hit_any(answer_text, CON_HINTS) else 0
        if not con_flag and len(answer_text or "") >= 80:
            con_flag = 1

        # 상대경로로 map flow 찾기
        map_flow_path = os.path.normpath(os.path.join(current_dir, "..", "..", "standard", "map_answer_to_materials", "flow.dag.yaml"))
        mapping_path = os.path.join(os.path.dirname(__file__), "data", "material_id_mapping.json")
        materials_list = _build_materials_list_from_mapping(mapping_path)

        llm_items = _call_llm_map_flow(map_flow_path, answer_text, materials_list, current_material_full, list(current_material_id) if current_material_id else [])

        # 소재 매칭
        for item in llm_items:
            if not isinstance(item, dict) or not item.get("material"):
                continue
            
            material_id = item["material"]
            
            # material_id는 [cat, chunk, mat] 형태여야 함
            if not isinstance(material_id, list) or len(material_id) != 3:
                continue
            
            # 소재 이름 찾기
            cat_num, chunk_num, mat_num = material_id
            temp_cat = engine.categories.get(cat_num)
            if not temp_cat:
                continue
            
            temp_chunk = temp_cat.chunks.get(chunk_num)
            if not temp_chunk:
                continue
            
            temp_mat = temp_chunk.materials.get(mat_num)
            if not temp_mat:
                continue
            
            material_name = f"{temp_cat.category_name} {temp_chunk.chunk_name} {temp_mat.name}"
            matched_materials.append(material_name)
            axes_analysis_by_material[material_name] = item.get("axes", {})
            mapped_ids.append(material_id)

        # LLM 분석 결과 반영
        for i, material_id in enumerate(mapped_ids):
            cat_num, chunk_num, mat_num = material_id
            material = engine._get_material(cat_num, chunk_num, mat_num)
            if not material:
                continue

            axes_data = axes_analysis_by_material.get(matched_materials[i], {})
            is_pass = axes_data.get("pass", 0) == 1

            if is_pass:
                # 회피/반감 응답: 소재 완료 처리
                material.principle = [1, 1, 1, 1, 1, 1]
                material.example, material.similar_event = 1, 1
                material.count = 1
                logger.info(f"회피/반감 감지: {matched_materials[i]} - 소재 완료 처리")

        # 상대경로로 map flow 찾기
        map_flow_path = os.path.normpath(os.path.join(current_dir, "..", "..", "standard", "map_answer_to_materials", "flow.dag.yaml"))
        mapping_path = os.path.join(os.path.dirname(__file__), "data", "material_id_mapping.json")
        materials_list = _build_materials_list_from_mapping(mapping_path)

        llm_items = _call_llm_map_flow(map_flow_path, answer_text, materials_list, current_material_full, list(current_material_id) if current_material_id else [])

        # 소재 매칭
        for item in llm_items:
            if not isinstance(item, dict) or not item.get("material"):
                continue
            
            material_id = item["material"]
            
            # material_id는 [cat, chunk, mat] 형태여야 함
            if not isinstance(material_id, list) or len(material_id) != 3:
                continue
            
            # 소재 이름 찾기
            cat_num, chunk_num, mat_num = material_id
            temp_cat = engine.categories.get(cat_num)
            if not temp_cat:
                continue
            
            temp_chunk = temp_cat.chunks.get(chunk_num)
            if not temp_chunk:
                continue
            
            temp_mat = temp_chunk.materials.get(mat_num)
            if not temp_mat:
                continue
            
            material_name = f"{temp_cat.category_name} {temp_chunk.chunk_name} {temp_mat.name}"
            matched_materials.append(material_name)
            axes_analysis_by_material[material_name] = item.get("axes", {})
            mapped_ids.append(material_id)

        # LLM 분석 결과 반영
        for i, material_id in enumerate(mapped_ids):
            cat_num, chunk_num, mat_num = material_id
            material = engine._get_material(cat_num, chunk_num, mat_num)
            if not material:
                continue

            axes_data = axes_analysis_by_material.get(matched_materials[i], {})
            is_pass = axes_data.get("pass", 0) == 1

            if is_pass:
                # 회피/반감 응답: 소재 완료 처리
                material.principle = [1, 1, 1, 1, 1, 1]
                material.example, material.similar_event = 1, 1
                material.count = 1
                logger.info(f"회피/반감 감지: {matched_materials[i]} - 소재 완료 처리")
            else:
                # 정상 응답 - principle (6W)
                principle = axes_data.get("principle", [])
                if isinstance(principle, list) and len(principle) == 6:
                    for j, val in enumerate(principle):
                        if val == 1: material.principle[j] = 1
                else:
                    # 휴리스틱 보조
                    for j, val in enumerate(axes_evidence.values()):
                        if val and j < 6: material.principle[j] = 1

                # example / similar_event
                if axes_data.get("example") == 1 or ex_flag: material.example = 1
                if axes_data.get("similar_event") == 1 or con_flag: material.similar_event = 1
                
                # count 증가 (정상 응답)
                material.count += 1

            # 카테고리 가중치 갱신
            category = engine.categories[cat_num]
            category.chunk_weight[chunk_num] = category.chunk_weight.get(chunk_num, 0) + 1
            material.mark_filled_if_ready()

        logger.info(f"🔍 [소재 매칭] {current_material} → {matched_materials}")
    
    # ------------------ 다음 질문 생성 ------------------

    try:
        material_id = engine.select_material()
        cat_num, chunk_num, mat_num = material_id


        material = engine._get_material(cat_num, chunk_num, mat_num)
        if not material:
            return {"next_question": None, "last_answer_materials_id": []}

        # Material Gate 체크: 소재에 기존 데이터가 없으면 gate 질문 먼저
            return {"next_question": None, "last_answer_materials_id": []}

        # Material Gate 체크: 소재에 기존 데이터가 없으면 gate 질문 먼저
        category = engine.categories[cat_num]
        chunk = category.chunks[chunk_num]
        full_material_name = f"{category.category_name} {chunk.chunk_name} {material.name}"
        
        # 직전 질문이 gate가 아니고, 현재 소재가 완전히 비어있으면 gate 질문 생성
        # 단, 직전 질문이 gate였어도 다른 소재로 바뀌었으면 gate 질문 생성
        last_question_type = question.get("type") if question else None
        # material_id는 material.full_material_id 또는 최상위 material_id에서 가져오기
        last_material_id = None
        if isinstance(current_material, dict):
            last_material_id = tuple(current_material.get("full_material_id", [])) if current_material.get("full_material_id") else None
        if not last_material_id:
            last_material_id = tuple(question.get("material_id")) if question and question.get("material_id") else None
        is_material_empty = (material.progress_score() == 0 and material.count == 0)
        is_different_material = (last_material_id != material_id)
        
        
        if is_material_empty and (last_question_type != "material_gate" or is_different_material):
            gate_question_text = generate_material_gate_question(full_material_name)
            
            # material.name 직접 사용
            material_name = material.name
            
            next_question = {
                "id": f"q-{uuid4().hex[:8]}",
                "material": {
                    "full_material_name": full_material_name,
                    "full_material_id": list(material_id),
                    "material_name": material_name,
                    "material_order": material.order
                },
                "type": "material_gate",
                "text": gate_question_text
            }
            
            # 메트릭 업데이트 (상태는 변경하지 않음)
            updated_metrics = {
                "session_id": sessionId,
                "categories": serialize_categories(engine.categories),
                "engine_state": {
                    "last_material_id": list(engine.state.last_material_id) if engine.state.last_material_id else [],
                    "last_material_streak": engine.state.last_material_streak,
                    "epsilon": engine.state.epsilon
                },
                "asked_total": metrics.get("asked_total", 0) + 1,
                "policy_version": "v0.5.0"
            }
            
            # Delta 계산 및 발행
            previous_categories = metrics.get("categories", [])
            publish_delta(previous_categories, updated_metrics, user_id, autobiography_id)
            
            session_update = {
                "metrics": updated_metrics,
                "last_question": next_question,
                "updated_at": time.time()
            }
            redis_client.setex(session_key, 3600, json.dumps(session_update))
            
            logger.info(f"🚧 [Material Gate] {full_material_name} - 진입 확인 질문 생성")
            if last_question_type == "material_gate" and is_different_material:
                logger.debug(f"직전도 gate였지만 소재 변경: {last_material_id} → {material_id}")
            
            return {"next_question": next_question, "last_answer_materials_id": mapped_ids if mapped_ids else []}

        material_id, target = engine.select_question_in_material(material_id)
        if not target:
            return {"next_question": None, "last_answer_materials_id": []}
        
        
        # 소재가 변경되었는지 확인
        if material_id != (cat_num, chunk_num, mat_num):
            # 변경된 소재 다시 가져오기
            cat_num, chunk_num, mat_num = material_id
            material = engine._get_material(cat_num, chunk_num, mat_num)
            category = engine.categories[cat_num]
            chunk = category.chunks[chunk_num]
            full_material_name = f"{category.category_name} {chunk.chunk_name} {material.name}"

        # 타입 매핑: 엔진 타입 → 프롬프트 타입
        type_mapping = {
            "w1": "when_where",
            "w2": "how1",
            "w3": "who",
            "w4": "what",
            "w5": "how2",
            "w6": "why",
            "ex": "ex",
            "con": "con"
        }
        prompt_type = type_mapping.get(target, target)

        # 카테고리가 같으면 이전 답변을 컨텍스트로 전달

        # 카테고리가 같으면 이전 답변을 컨텍스트로 전달
        context_answer = None
        if not is_first_question and last_material_id:
            last_cat_num = last_material_id[0] if isinstance(last_material_id, (list, tuple)) and len(last_material_id) >= 1 else None
            current_cat_num = material_id[0]
            if last_cat_num == current_cat_num:
                context_answer = answer_text
                logger.info(f"[CONTEXT] Using previous answer as context cat_num={current_cat_num}")
            else:
                logger.info(f"[CONTEXT] Category changed, no context cat_num={last_cat_num}->{current_cat_num}")

        question_text = generate_question_llm(full_material_name, prompt_type, context_answer)


        # streak 업데이트
        if engine.state.last_material_id == material_id:
            engine.state.last_material_streak += 1
        else:
            engine.state.last_material_id = material_id
            engine.state.last_material_streak = 1

        # material.name 직접 사용
        material_name = material.name
        
        next_question = {
            "id": f"q-{uuid4().hex[:8]}",
            "material": {
                "full_material_name": full_material_name,
                "full_material_id": list(material_id),
                "material_name": material_name,
                "material_order": material.order
            },
            "material": {
                "full_material_name": full_material_name,
                "full_material_id": list(material_id),
                "material_name": material_name,
                "material_order": material.order
            },
            "type": target,
            "text": question_text
        }

        updated_metrics = {
            "session_id": sessionId,
            "session_id": sessionId,
            "categories": serialize_categories(engine.categories),
            "engine_state": {
                "last_material_id": list(engine.state.last_material_id) if engine.state.last_material_id else [],
                "last_material_streak": engine.state.last_material_streak,
                "epsilon": engine.state.epsilon
            },
            "asked_total": metrics.get("asked_total", 0) + 1,
            "policy_version": "v0.5.0"
        }
        
        # Delta 계산 및 발행
        previous_categories = metrics.get("categories", [])
        publish_delta(previous_categories, updated_metrics, user_id, autobiography_id)

        session_update = {
            "metrics": updated_metrics,
            "last_question": next_question,
            "updated_at": time.time()
        }
        redis_client.setex(session_key, 3600, json.dumps(session_update))

        logger.info(f"🎯 [질문 생성] {category.category_name}-{chunk.chunk_name}-{material.name} ({target})")

        last_answer_materials_id = mapped_ids if mapped_ids else []
        return {"next_question": next_question, "last_answer_materials_id": last_answer_materials_id}
    except Exception as e:
        logger.error(f"질문 생성 실패: {e}")
        return {"next_question": None, "last_answer_materials_id": []}