from typing import Dict, List, Optional
from uuid import uuid4
from pathlib import Path
import logging
from .core import InterviewEngine

logger = logging.getLogger("interview_generators")

#V2 추가 함수 - 첫 질문 생성
def generate_first_question(engine: InterviewEngine, metrics: Dict) -> Dict:
    """
    첫 질문 생성 - 카테고리 소개 질문
    
    기존 Legacy 알고리즘은 바로 소재별 질문을 생성했지만,
    V2에서는 첫 질문에서 카테고리 전체에 대한 소개 질문을 먼저 생성.
    예: '가족에 대해서 어떤 이야기를 하고 싶으신가요?'
    """
    try:
        # 선호 카테고리가 있으면 모든 카테고리에 대해 질문
        preferred_categories = metrics.get("preferred_categories", [])
        if preferred_categories:
            # 선호 카테고리 이름들 수집
            category_names = []
            for cat_num in preferred_categories:
                category = engine.categories.get(cat_num)
                if category:
                    category_names.append(category.category_name)
            
            if category_names:
                categories_text = ", ".join(category_names)
                question_text = f"{categories_text}에 대해서 이야기하게 될 거에요. 어떤 이야기를 하고 싶으신가요?"
                selected_cat_num = preferred_categories[0]
            else:
                return {"next_question": None, "last_answer_materials_id": []}
        else:
            # 선호 카테고리가 없으면 그냥 어떤 이야기가 하고 싶냐고 물어봄
            question_text = "어떤 이야기를 하고 싶으신가요? 자유롭게 이야기 해주세요."
            selected_cat_num = 0
            category_names = []

        return {
            "next_question": {
                "id": f"q-{uuid4().hex[:8]}",
                "material": "첫 질문(material 없음)",
                "type": "category_intro",
                "text": question_text,
                "material_id": []
            },
            "last_answer_materials_id": []
        }
        
    except Exception as e:
        logger.error(f"첫 질문 생성 실패: {e}")
        return {"next_question": None, "last_answer_materials_id": []}

#V2 추가 함수 - LLM 질문 생성
def generate_question_llm(material: str, target: str, context_answer: Optional[str] = None) -> str:
    """LLM으로 질문 생성"""
    try:
        # 현재 파일 위치에서 프로젝트 루트의 flows 디렉토리로 이동
        current_dir = Path(__file__).parent.parent  # engine의 부모 (interview_chat_v2)
        ai_root = current_dir.parent.parent.parent.parent  # ai 디렉토리
        flow_path = ai_root / "flows" / "interviews" / "standard" / "generate_interview_questions_v2" / "flow.dag.yaml"
        
        if not flow_path.exists():
            logger.warning(f"Flow not found: {flow_path}")
            raise FileNotFoundError(f"Flow not found: {flow_path}")
        
        from promptflow import load_flow
        flow = load_flow(str(flow_path.absolute()))
        keywords = [context_answer] if context_answer is not None else []
        
        result = flow(
            material=material,
            type=target,
            keywords=keywords,
            tone="따뜻하고 존중하는 어조",
            max_len=120,
            model="gpt-4o-mini",
            temperature=0.8
        )
        
        # logger.debug(f"generate_question_llm result type: {type(result)}, value: {result}")
        
        # flow output: {"question": {"text": "...", ...}}
        if isinstance(result, dict):
            question_data = result.get("question", {})
            # logger.debug(f"question_data type: {type(question_data)}, value: {question_data}")
            if isinstance(question_data, dict):
                question_text = question_data.get("text", "")
            else:
                question_text = str(question_data)
        else:
            question_text = str(result)
            
        if question_text:
            return question_text
        else:
            logger.warning(f"LLM returned empty question for {material}, {target}")
            raise ValueError("Empty question returned")
            
    except Exception as e:
        logger.error(f"LLM 질문 생성 실패: {e}")
        logger.info(f"Using simple fallback for {material}, {target}")
        return f"{material}에 대해 더 자세히 이야기해 주세요."

#V2 추가 함수 - Material Gate 질문 생성
def generate_material_gate_question(full_material_name: str) -> str:
    """소재 진입 전 확인 질문 생성 (LLM)"""
    try:
        current_dir = Path(__file__).parent.parent
        flow_path = current_dir.parent.parent / "standard" / "generate_material_gate_question" / "flow.dag.yaml"
        
        if not flow_path.exists():
            logger.warning(f"Material gate flow not found: {flow_path}")
            raise FileNotFoundError(f"Flow not found: {flow_path}")
        
        from promptflow import load_flow
        flow = load_flow(str(flow_path.absolute()))
        
        result = flow(
            material=full_material_name,
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        # flow output: {"question": {"text": "...", ...}}
        if isinstance(result, dict):
            question_data = result.get("question", {})
            if isinstance(question_data, dict):
                question_text = question_data.get("text", "")
            else:
                question_text = str(question_data)
        else:
            question_text = str(result)
            
        if question_text:
            return question_text
        else:
            logger.warning(f"LLM returned empty gate question for {full_material_name}")
            raise ValueError("Empty question returned")
            
    except Exception as e:
        logger.error(f"Material gate 질문 생성 실패: {e}")
        logger.info(f"Using simple fallback for {full_material_name}")
        parts = full_material_name.split()
        material_name = parts[-1] if parts else full_material_name
        return f"{material_name}에 대해 이야기할 것이 있으신가요?"

#V2 추가 함수 - 테마 관리
class ThemeManager:
    def __init__(self, engine: InterviewEngine, theme_json: dict):
        self.engine = engine
        self.category_name_to_num: Dict[str, int] = {
            cat.category_name: cat.category_num for cat in engine.categories.values()
        }
        themes = {}
        for t in theme_json.get("theme", []):
            theme_name = t.get("name")
            cat_names = t.get("category", [])
            nums = [self.category_name_to_num[n] for n in cat_names if n in self.category_name_to_num]
            if nums:
                themes[theme_name] = nums
        self.themes = themes

    def select_theme(self, theme_name: str, initial_weight: int = 10, *, force: bool = False) -> List[int]:
        nums = self.themes.get(theme_name, [])
        if nums:
            self.engine.boost_theme(nums, initial_weight=initial_weight, force=force)
        return nums