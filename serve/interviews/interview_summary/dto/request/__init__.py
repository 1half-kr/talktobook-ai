from typing import List
from pydantic import BaseModel, Field


class ConversationDto(BaseModel):
    question: str = Field(description="질문 내용")
    conversation: str = Field(description="답변 내용")


class InterviewSummaryRequestDto(BaseModel):
    interviewId: int = Field(description="인터뷰 ID")
    userId: int = Field(description="사용자 ID")
    conversations: List[ConversationDto] = Field(description="인터뷰 대화 내역")
