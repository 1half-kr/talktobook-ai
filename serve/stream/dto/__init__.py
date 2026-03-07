from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from typing import List

# AI 인터뷰 질의응답에 대한 payload 정의
class Conversation(BaseModel):
    content: str
    conversationType: str
    materials: Optional[str] = ""
    
class InterviewQuestion(BaseModel):
    questionText: str
    questionOrder: int
    materials: Optional[str] = ""

class InterviewPayload(BaseModel):
    autobiographyId: int
    userId: int
    conversation: Optional[list[Conversation]] = []
    interviewQuestion: Optional[InterviewQuestion]

# Categories와 하위 데이터들에 대한 payload 정의

class ChunksPayload(BaseModel):
    categoryId: int
    chunkOrder: int
    weight: int
    timestamp: datetime

class MaterialsPayload(BaseModel):
    chunkId: int
    materialOrder: int
    example: int
    similarEvent: int
    count: int
    principle: List[int] = Field(default=[0,0,0,0,0,0])
    timestamp: datetime

class CategoriesPayload(BaseModel):
    autobiographyId: int
    userId: int
    themeId: int  # 추가된 필드
    categoryId: int
    chunks: Optional[list[ChunksPayload]] = []
    materials: Optional[list[MaterialsPayload]] = []
    
    
# 자서전 Generate를 위한 사용자 정보와 answers 정의
class UserInfo(BaseModel):
    gender: str
    occupation: str
    ageGroup: str

class AutobiographyInfo(BaseModel):
    theme: str
    reason: str
    category: str

class InterviewAnswer(BaseModel):
    content: str
    conversationType: str

class InterviewAnswersPayload(BaseModel):
    cycleId: Optional[str] = None
    step: Optional[int] = 1
    autobiographyId: int
    userId: int
    userInfo: UserInfo
    autobiographyInfo: AutobiographyInfo
    answers: List[InterviewAnswer]
    
# generate 자서전에 대한 response payload 정의
class GeneratedAutobiographyPayload(BaseModel):
    cycleId: Optional[str] = None
    step: Optional[int] = None
    autobiographyId: int
    userId: int
    title: str
    content: str
    
# interview에 대한 요약 응답 payload 정의
class InterviewSummaryResponsePayload(BaseModel):
    interviewId: int
    userId: int
    summary: str