from pydantic import BaseModel, Field


class InterviewSummaryResponseDto(BaseModel):
    summary: str = Field(description="인터뷰 요약 내용")
