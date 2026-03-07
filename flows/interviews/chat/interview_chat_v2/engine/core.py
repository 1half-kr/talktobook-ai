from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional, Iterable
import random
import logging

logger = logging.getLogger("interview_engine")

MaterialId = Tuple[int, int, int]  # (category_num, chunk_num, order)

#기존 알고리즘 - 모델
@dataclass
class Material:
    order: int
    name: str
    principle: List[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])  # w1..w6
    example: int = 0
    similar_event: int = 0
    count: int = 0

    def sum_principle(self) -> int:
        return sum(self.principle)
    
    def progress_score(self) -> int:
        return self.sum_principle() + self.example + self.similar_event

    def mark_filled_if_ready(self) -> None:
        w1, w2, w3, w4, w5, w6 = self.principle
        if self.sum_principle() >= 3 and self.example == 1 and self.similar_event == 1 and (w5 == 1):
            self.count = 1
    
    def is_fully_completed(self) -> bool:
        return all(v == 1 for v in self.principle) and self.example == 1 and self.similar_event == 1

@dataclass
class Chunk:
    chunk_num: int
    chunk_name: str
    materials: Dict[int, Material] = field(default_factory=dict)

@dataclass
class Category:    
    category_num: int
    category_name: str
    chunks: Dict[int, Chunk] = field(default_factory=dict)
    chunk_weight: Dict[int, int] = field(default_factory=dict)

    def ensure_weights(self) -> None:
        for ch_num in self.chunks.keys():
            self.chunk_weight.setdefault(ch_num, 0)

@dataclass
class EngineState:
    last_material_id: Optional[MaterialId] = None
    last_material_streak: int = 0
    epsilon: float = 0.05

#기존 알고리즘 - 메인 엔진
class InterviewEngine:
    def __init__(self, categories: Dict[int, Category], m_ratio: float = 0.70, n_chars_target: int = 50_000):
        self.categories = categories
        self.m_ratio = m_ratio
        self.n_chars_target = n_chars_target
        self.state = EngineState()      
        self.theme_initialized: bool = False

        for cat in self.categories.values():
            cat.ensure_weights()

    #기존 알고리즘 - 테마 부스트
    def boost_theme(self, category_nums: Iterable[int], initial_weight: int = 10, *, force: bool = False) -> None:
        if self.theme_initialized and not force:
            return
        for cnum in category_nums:
            cat = self.categories.get(cnum)
            if not cat:
                continue
            for ch_num in cat.chunks.keys(): 
                if cat.chunk_weight.get(ch_num, 0) == 0:
                    cat.chunk_weight[ch_num] = initial_weight
        self.theme_initialized = True       
            
    #기존 알고리즘 - 소재 선택
    def select_material(self) -> MaterialId:
        # 1) 직전 소재 유지
        if self.state.last_material_id: 
            cat, ch, m = self.state.last_material_id
            mat = self._get_material(cat, ch, m)
            if mat:
                if self.state.last_material_streak < 3 and mat.count < 1:
                    logger.debug(f"직전 소재 유지: {self.state.last_material_id} (streak={self.state.last_material_streak})")
                    return self.state.last_material_id

        # 2) ε-greedy 탐색
        rand_val = random.random()
        if rand_val < self.state.epsilon:
            result = self._random_material_id()
            logger.debug(f"랜덤 선택: {result}")
            return result

        # 3) 우선순위 선택
        result = self._select_priority_material()
        logger.info(f"소재 선택: {result}")
        return result
    
    def _select_priority_material(self) -> MaterialId:
        """우선순위 기반 소재 선택 (미완료 소재만)"""
        # 후보 목록 구축 (미완료 소재만)
        candidates = [] 
        for cat in self.categories.values():
            for ch_num, ch in cat.chunks.items():
                cw = cat.chunk_weight.get(ch_num, 0)
                for m_num, mat in ch.materials.items():
                    if not mat.is_fully_completed():  # 미완료 소재만
                        candidates.append({
                            "id": (cat.category_num, ch_num, m_num),
                            "chunk": ch_num,
                            "cw": cw,
                            "sumwc": mat.progress_score(),
                        }) 
        
        if not candidates:
            # 모든 소재가 완료된 경우 - 무작위 선택
            return self._random_material_id()

        # 정렬: chunk_weight DESC, sumw ASC, category_num ASC
        candidates.sort(key=lambda x: (-x["cw"], x["sumwc"], x["id"][0]))

        # 동률 처리
        best_group = [candidates[0]]
        for c in candidates[1:]:
            same_weight = (c["cw"] == best_group[0]["cw"])
            same_chunk  = (c["chunk"] == best_group[0]["chunk"])
            same_sumwc   = (c["sumwc"] == best_group[0]["sumwc"])
            if same_weight and same_chunk and same_sumwc:
                best_group.append(c)
            else:
                break
        return random.choice(best_group)["id"]

    #기존 알고리즘 - 질문 타입 선택 (재선택 로직 포함)
    def select_question_in_material(self, material_id: MaterialId) -> Tuple[MaterialId, str]:
        """소재에서 질문 타입 선택, 완료시 재선택"""
        material = self._get_material(*material_id)
        if not material:
            raise RuntimeError(f"Material not found: {material_id}")
            
        # 완료된 소재면 새 소재 선택
        if material.is_fully_completed():
            new_id = self._select_priority_material()
            material = self._get_material(*new_id)
            material_id = new_id
            if not material or material.is_fully_completed():
                # 모든 소재가 완료된 경우
                return material_id, "general"

        w1, w2, w3, w4, w5, w6 = material.principle
        needs: List[str] = []
        if w5 == 0: needs.append("w5")
        if material.example == 0: needs.append("ex")
        if material.similar_event == 0: needs.append("con")
        for label, val in [("w1", w1), ("w3", w3), ("w4", w4), ("w2", w2), ("w6", w6)]:
            if val == 0:
                needs.append(label)

        if not needs:
            return material_id, "general"

        return material_id, needs[0]  # (소재ID, 타입) 반환

    #기존 알고리즘 - 답변 후 업데이트
    def update_after_answer(self, mapped_ids: Iterable[MaterialId], current_id: MaterialId) -> None:
        for (cnum, chnum, mnum) in mapped_ids:
            mat = self._get_material(cnum, chnum, mnum)
            if not mat:
                continue

            mat.principle = [min(v + 1, 1) for v in mat.principle]
            mat.example, mat.similar_event = 1, 1
            mat.mark_filled_if_ready()
            cat = self.categories[cnum]
            cat.chunk_weight[chnum] = cat.chunk_weight.get(chnum, 0) + 1

        if self.state.last_material_id == current_id:
            self.state.last_material_streak += 1 
        else:
            self.state.last_material_id = current_id
            self.state.last_material_streak = 1

    #기존 알고리즘 - 종료 조건
    def should_stop(self, transcript_len: int) -> bool:
        cond_a = self._count_filled_materials() >= 30
        cond_b = self._categories_meet_ratio(self.m_ratio)
        cond_c = (transcript_len * 0.75) >= self.n_chars_target
        return cond_a and (cond_b or cond_c)

    #기존 알고리즘 - 헬퍼 함수들
    def _get_material(self, cnum: int, chnum: int, mnum: int) -> Optional[Material]:
        cat = self.categories.get(cnum)
        if not cat:
            return None
        ch = cat.chunks.get(chnum)
        if not ch:
            return None
        return ch.materials.get(mnum)

    def _random_material_id(self) -> MaterialId:
        cat = random.choice(list(self.categories.values()))
        ch = random.choice(list(cat.chunks.values()))
        mat = random.choice(list(ch.materials.values()))
        return (cat.category_num, ch.chunk_num, mat.order)

    def _count_filled_materials(self) -> int:
        return sum(
            1
            for cat in self.categories.values()
            for ch in cat.chunks.values()
            for mat in ch.materials.values()
            if mat.count == 1
        )

    def _categories_meet_ratio(self, ratio: float) -> bool:
        for cat in self.categories.values():
            mats = []
            for ch in cat.chunks.values():
                for m in ch.materials.values():
                    mats.append(m)

            if not mats:
                continue
            
            filled = sum(1 for m in mats if m.count == 1) 
            coverage = filled / len(mats)
            
            if coverage < ratio:
                return False
        return True

    #기존 알고리즘 - LLM 연동 지점
    def map_answer_to_materials(self, answer: str, current_id: MaterialId) -> List[MaterialId]:
        """LLM 연동 지점 - 답변을 소재에 매핑"""
        return [current_id]

    def generate_question(self, material: Material, target: str) -> str:
        """LLM 연동 지점 - 질문 생성"""
        six = {
            "w1": "언제/어디서", "w2": "어떻게(방법)", "w3": "누가", 
            "w4": "무엇을", "w5": "어떻게(감정)", "w6": "왜",
        }
        if target in six:
            return f"{material.name}에 대해 '{six[target]}' 측면에서 더 구체적으로 들려주세요."
        if target == "ex":
            return f"{material.name}와 관련된 구체적인 '예시 한 가지'를 자세히 이야기해 주세요."
        if target == "con":
            return f"{material.name}와 비슷한 '유사 사례'가 있었다면 비교해서 설명해 주세요."
        return f"{material.name}에 대해 아직 다루지 못한 세부사항이나 감정, 맥락을 더 이야기해 주세요."

    #V2 추가 함수 - JSON에서 카테고리 빌드
    @staticmethod
    def build_categories_from_category_json(kor_json: dict) -> Dict[int, Category]:
        categories: Dict[int, Category] = {}
        cat_num = 1

        for cat_entry in kor_json.get("category", []):
            cat_name = cat_entry.get("name")
            chunks: Dict[int, Chunk] = {}
            ch_num = 1

            for ch_entry in cat_entry.get("chunk", []):               
                ch_name = ch_entry.get("name")
                materials: Dict[int, Material] = {}
                m_num = 1

                for mat_entry in ch_entry.get("material", []):
                    # mat_entry가 dict면 name 추출, 아니면 그대로 사용
                    if isinstance(mat_entry, dict):
                        mat_name = mat_entry.get("name", "")
                        mat_order = mat_entry.get("order", m_num)
                    else:
                        mat_name = str(mat_entry)
                        mat_order = m_num
                    
                    materials[mat_order] = Material(
                        order=mat_order,
                        name=mat_name
                    )
                    m_num += 1

                chunks[ch_num] = Chunk(
                    chunk_num=ch_num,
                    chunk_name=str(ch_name),
                    materials=materials
                )
                ch_num += 1

            category = Category(
                category_num=cat_num,
                category_name=str(cat_name),
                chunks=chunks
            )
            category.ensure_weights()
            categories[cat_num] = category
            cat_num += 1

        return categories