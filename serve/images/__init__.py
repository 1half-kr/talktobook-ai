from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

# serve 폴더를 sys.path에 추가
sys.path.append(str(Path(__file__).parent.parent))
from auth import AuthRequired

from promptflow import load_flow

# flow 경로
current_dir = Path(__file__).parent.parent.parent
flow_path = current_dir / "flows" / "gen_image" / "flow.dag.yaml"

router = APIRouter()

# flow 로드
flow = load_flow(str(flow_path))

# DTO 정의
class ImageGenerationRequest(BaseModel):
    autobiography_content: str
    chapter_title: Optional[str] = "부모님과 행복했던 나날"
    style: Optional[str] = "vivid"
    
    class Config:
        schema_extra = {
            "example": {
                "autobiography_content": "어머니와의 소중한 추억들은 제 삶의 가장 따뜻한 뿌리입니다. 어린 시절의 집은 늘 아침 냄새로 가득했어요.",
                "chapter_title": "부모님과 행복했던 나날",
                "style": "vivid"
            }
        }


class ImageGenerationResponse(BaseModel):
    image_url: str
    chapter_title: Optional[str] = "부모님과 행복했던 나날"

# 이미지 생성 엔드포인트
@router.post("/api/v2/images/generate", 
             response_model=ImageGenerationResponse,
             summary="이미지 생성",
             dependencies=[Depends(AuthRequired())],
             description="텍스트 프롬프트를 기반으로 이미지를 생성합니다.",
             tags=["이미지 생성 (Image Generation)"])
async def generate_image(request: ImageGenerationRequest):
    """이미지 생성 API"""
    try:
        result = flow(
            autobiography_content=request.autobiography_content,
            style=request.style
        )
        
        image_url = result.get("image_url")

        
        if not image_url or image_url.startswith("Error:"):
            raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {image_url}")
        
        return ImageGenerationResponse(
            image_url=image_url,
            chapter_title=request.chapter_title
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")