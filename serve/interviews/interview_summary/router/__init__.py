from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
import sys
from pathlib import Path

from auth import get_current_user, AuthRequired
from ..dto.request import InterviewSummaryRequestDto
from ..dto.response import InterviewSummaryResponseDto
from stream.dto import (
    InterviewSummaryRequestDto as StreamInterviewSummaryRequestDto,
    InterviewSummaryResponsePayload,
)
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


def _run_summary_flow(conversations) -> str:
    """conversations 리스트를 flow에 넘겨 요약 문자열을 반환하는 공통 헬퍼."""
    result = flow(conversation=[conv.model_dump() for conv in conversations])
    summary = result.get("summary", "")
    if hasattr(summary, '__iter__') and not isinstance(summary, str):
        summary = ''.join(summary)
    return str(summary)


def summarize_interview_fn(request_dto: StreamInterviewSummaryRequestDto) -> InterviewSummaryResponsePayload:
    """함수로 직접 호출 가능한 인터뷰 요약 함수.

    StreamInterviewSummaryRequestDto를 입력으로 받아 PromptFlow를 실행하고,
    InterviewSummaryResponsePayload를 반환한다.
    MQ Consumer 등 API 외부에서 호출할 때 사용한다.
    """
    logger.info(
        f"[SUMMARY_FN] Starting - interview_id={request_dto.interviewId} "
        f"user_id={request_dto.userId} conversations={len(request_dto.conversations)}"
    )
    summary = _run_summary_flow(request_dto.conversations)
    logger.info(f"[SUMMARY_FN] Done - interview_id={request_dto.interviewId} summary_len={len(summary)}")
    return InterviewSummaryResponsePayload(
        interviewId=request_dto.interviewId,
        userId=request_dto.userId,
        summary=summary,
    )


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
        summary = _run_summary_flow(requestDto.conversations)
        return InterviewSummaryResponseDto(summary=summary)

    except Exception as e:
        logger.error(f"Interview summary error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"error 발생: {str(e)}")
