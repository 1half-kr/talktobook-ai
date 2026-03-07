from pydantic import BaseModel, Field


class AutobiographyGenerateResponseDto(BaseModel):
    title: str = Field(description="자동 생성된 자서전 제목", example="나의 대학 시절, 꿈을 향한 첫걸음")
    autobiographical_text: str = Field(description="AI가 생성한 자서전 본문", example="대학교 1학년 때 처음 프로그래밍을 접했을 때의 설렘은 지금도 잊을 수 없다. 그 작은 'Hello World'가 내 인생을 바꾼 시작점이었다...")
