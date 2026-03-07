from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ===== Shared DTOs =====
class MaterialDto(BaseModel):
    order: int
    name: str
    principle: List[int] = Field(default=[0, 0, 0, 0, 0, 0])
    example: int = 0
    similar_event: int = 0
    count: int = 0


class ChunkDto(BaseModel):
    chunk_num: int
    chunk_name: str
    chunk_weight: int = 0
    materials: List[MaterialDto] = Field(default_factory=list)


class CategoryDto(BaseModel):
    category_num: int
    category_name: str
    chunks: List[ChunkDto] = Field(default_factory=list)


class EngineStateDto(BaseModel):
    last_material_id: Optional[List[int]] = Field(default=None)
    last_material_streak: int = 0
    epsilon: float = 0.10


class MetricsDto(BaseModel):
    session_id: str
    categories: List[CategoryDto]
    engine_state: EngineStateDto = Field(default_factory=EngineStateDto)
    asked_total: int = 0
    policy_version: str = "v0.5.0"


# ===== Session Start DTOs =====
class SessionStartRequestDto(BaseModel):
    preferred_categories: List[int] = Field(default_factory=list)
    previous_metrics: Optional[MetricsDto] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "preferred_categories": [1, 3, 5]
            }
        }


class SessionStartResponseDto(BaseModel):
    first_question: Optional[Dict[str, Any]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "first_question": {
                    "id": "q-fcf8ea8c",
                    "material": "좋아했던 과목",
                    "type": "w1",
                    "text": "좋아했던 과목에 대해 '언제' 측면에서 더 구체적으로 들려주세요. 어느 시기에 그 과목을 좋아하게 되셨나요?",
                    "material_id": [1, 1, 1]
                }
            }
        }


# ===== Turn DTOs =====
class InterviewChatV2RequestDto(BaseModel):
    answer_text: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer_text": "대학교 2학년 때 컴퓨터과학 수업을 들으면서 프로그래밍에 흥미를 느끼기 시작했어요. 처음에는 어려웠지만 교수님이 차근차근 설명해주시고, 실습을 통해 직접 코드를 작성해보면서 점점 재미를 느끼게 되었습니다. 특히 첫 번째 프로그램이 성공적으로 실행됐을 때의 성취감은 정말 잊을 수 없어요."
            }
        }


class InterviewChatV2ResponseDto(BaseModel):
    next_question: Optional[Dict[str, Any]]
    last_answer_materials_id: List[List[int]] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "next_question": {
                    "id": "q-def456",
                    "material": "좋아했던 과목",
                    "type": "ex",
                    "text": "프로그래밍 수업과 관련된 구체적인 '예시 한 가지'를 자세히 이야기해 주세요. 어떤 프로젝트나 과제가 특히 기억에 남나요?",
                    "material_id": [1, 1, 1]
                },
                "last_answer_materials_id": [[1, 1, 1], [1, 2, 3], [2, 1, 1]]
            }
        }


# ===== Session End DTOs =====
class SessionEndRequestDto(BaseModel):
    pass


class SessionEndResponseDto(BaseModel):
    session_id: str
    final_metrics: Optional[MetricsDto]
    pool_to_save: List[Dict[str, Any]] = Field(default_factory=list)