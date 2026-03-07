from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
import sys
from pathlib import Path

from auth import get_current_user, AuthRequired
from ..dto.request import InterviewSummaryRequestDto
from ..dto.response import InterviewSummaryResponseDto
from logs import get_logger

# flow 경로 추가
current_dir = Path(__file__).parent.parent.parent.parent.parent
flows_dir = current_dir / "flows" / "interview_summary" / "standard" / "summarize_interview"
sys.path.insert(0, str(flows_dir))

from promptflow import load_flow

logger = get_logger()

router = APIRouter()

# flow 로드
flow_path = flows_dir / "flow.dag.yaml"
flow = load_flow(str(flow_path))


@router.post(
    "/{interview_id}/summary",
    dependencies=[Depends(AuthRequired())],
    response_model=InterviewSummaryResponseDto,
    summary="인터뷰 요약",
    description="인터뷰 대화 내역을 입력받아 요약을 생성합니다.",
    tags=["인터뷰 (Interview)"],
)
async def summarize_interview(
    request: Request,
    requestDto: InterviewSummaryRequestDto,
):
    try:
        current_user = get_current_user(request)
        
        result = flow(
            conversation=[conv.model_dump() for conv in requestDto.conversation]
        )
        
        summary = result.get("summary", "")
        
        if hasattr(summary, '__iter__') and not isinstance(summary, str):
            summary = ''.join(summary)
        
        return InterviewSummaryResponseDto(summary=str(summary))

    except Exception as e:
        logger.error(f"Interview summary error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"error 발생: {str(e)}")
