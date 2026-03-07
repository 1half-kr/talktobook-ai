import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from promptflow.core import Flow
import asyncio
from pydantic_core import ValidationError
from starlette.requests import Request

from auth import MemberRole, get_current_user, AuthRequired
from autobiographies.generate_autobiography.dto.request import (
    AutobiographyGenerateRequestDto,
    UserInfoDto,
    AutobiographyInfoDto,
    InterviewContentDto,
)
from autobiographies.generate_autobiography.dto.response import (
    AutobiographyGenerateResponseDto,
)
from stream.dto import InterviewAnswersPayload, GeneratedAutobiographyPayload, CycleInitMessage
from constants import ConversationType
from session_manager import SessionManager
from logs import get_logger

logger = get_logger()

router = APIRouter()

# flow 경로 추가
current_dir = Path(__file__).parent.parent.parent.parent.parent
flows_dir = current_dir / "flows" / "autobiographies" / "standard" / "generate_autobiography"
sys.path.insert(0, str(flows_dir))

# flow 로드
flow_path = flows_dir / "flow.dag.yaml"
flow = Flow.load(str(flow_path))

_session_manager = SessionManager()


def _parse_flow_result(result: dict, default_title: str, default_text: str):
    """PromptFlow 실행 결과에서 title, text를 추출하는 공통 헬퍼."""
    title, text = default_title, default_text
    if isinstance(result, dict) and "result" in result:
        flow_output = result["result"]
        if hasattr(flow_output, '__iter__') and not isinstance(flow_output, str):
            try:
                flow_output = ''.join(flow_output)
            except Exception as gen_error:
                logger.error(f"[FLOW] Failed to join generator output: {gen_error}")
                flow_output = default_text
        try:
            parsed = json.loads(str(flow_output))
            if isinstance(parsed, dict):
                title = parsed.get("title", title)
                text = parsed.get("autobiographical_text", text)
        except json.JSONDecodeError:
            text = str(flow_output) if flow_output else text
    return title, text


def generate_autobiography_fn(payload: InterviewAnswersPayload) -> GeneratedAutobiographyPayload:
    """함수로 직접 호출 가능한 자서전 생성 함수.

    InterviewAnswersPayload를 입력으로 받아 PromptFlow를 실행하고,
    cycle 완료 여부를 Redis에서 확인한 뒤 GeneratedAutobiographyPayload를 반환한다.
    """
    logger.info(
        f"[GENERATE_FN] Starting - autobiography_id={payload.autobiographyId} "
        f"user_id={payload.userId} cycle_id={payload.cycleId} step={payload.step}"
    )

    user_info = UserInfoDto(
        gender=payload.userInfo.gender,
        occupation=payload.userInfo.occupation,
        age_group=payload.userInfo.ageGroup,
    )
    autobiography_info = AutobiographyInfoDto(
        theme=payload.autobiographyInfo.theme,
        reason=payload.autobiographyInfo.reason,
        category=payload.autobiographyInfo.category,
    )
    interviews = [
        InterviewContentDto(
            content=answer.content,
            conversation_type=ConversationType(answer.conversationType),
        )
        for answer in payload.answers
    ]

    default_title = f"{autobiography_info.theme} - {autobiography_info.category}에 대한 나의 이야기"
    default_text = "자서전 생성 완료"

    result = flow(
        user_info=user_info.dict(),
        autobiography_info=autobiography_info.dict(),
        interviews=[i.dict() for i in interviews],
        autobiography_id=payload.autobiographyId,
    )

    title, text = _parse_flow_result(result, default_title, default_text)
    logger.info(f"[GENERATE_FN] Flow done - autobiography_id={payload.autobiographyId} title_len={len(title)} text_len={len(text)}")

    # cycle 완료 여부 판단
    is_last = False
    if payload.cycleId:
        is_last = _session_manager.increment_and_check_cycle(payload.cycleId)

    return GeneratedAutobiographyPayload(
        cycleId=payload.cycleId,
        step=payload.step,
        autobiographyId=payload.autobiographyId,
        userId=payload.userId,
        title=str(title),
        content=str(text),
        isLast=is_last,
    )


@router.post(
    "/generate/{autobiography_id}",
    dependencies=[Depends(AuthRequired())],
    response_model=AutobiographyGenerateResponseDto,
    summary="자서전 생성",
    description="유저의 정보와 인터뷰 대화 내역을 입력받아 자서전을 생성합니다.",
    tags=["자서전 (Autobiography)"],
)
async def generate_autobiography(
    autobiography_id: int,
    request: Request,
    requestDto: AutobiographyGenerateRequestDto,
):
    try:
        current_user = get_current_user(request)
        user_id = current_user.get('memberId')
        logger.info(f"[GENERATE] Starting autobiography generation - autobiography_id={autobiography_id} user_id={user_id} interviews_count={len(requestDto.interviews)}")
        logger.info(f"[GENERATE] Theme={requestDto.autobiography_info.theme} Category={requestDto.autobiography_info.category}")
        
        # 인터뷰 데이터 통계
        total_chars = sum(len(interview.content) for interview in requestDto.interviews)
        logger.info(f"[GENERATE] Total interview content length: {total_chars} characters")
        
        logger.info(f"[FLOW] Executing autobiography generation flow")
        result = flow(
            user_info=requestDto.user_info.dict(),
            autobiography_info=requestDto.autobiography_info.dict(),
            interviews=[interview.dict() for interview in requestDto.interviews],
            autobiography_id=autobiography_id
        )
        
        # 기본값
        title = f"{requestDto.autobiography_info.theme} - {requestDto.autobiography_info.category}에 대한 나의 이야기"
        text = "인터뷰 내용을 바탕으로 자서전을 생성하는 중입니다..."
        
        # Flow 결과 처리
        if isinstance(result, dict) and "result" in result:
            flow_output = result["result"]
            
            # Generator 처리
            if hasattr(flow_output, '__iter__') and not isinstance(flow_output, str):
                try:
                    flow_output = ''.join(flow_output)
                    logger.debug(f"[FLOW] Joined generator output, length={len(flow_output)}")
                except Exception as gen_error:
                    logger.error(f"[ERROR] Failed to join generator output: {gen_error}")
                    flow_output = "자서전 생성 중 오류 발생"
            
            try:
                parsed = json.loads(str(flow_output))
                if isinstance(parsed, dict):
                    title = parsed.get("title", title)
                    text = parsed.get("autobiographical_text", text)
                    logger.info(f"[RESULT] Generated autobiography - autobiography_id={autobiography_id} title_length={len(title)} text_length={len(text)}")
                else:
                    logger.warning(f"[WARN] Parsed output is not dict, type={type(parsed)}")
            except json.JSONDecodeError as json_err:
                logger.warning(f"[WARN] Failed to parse flow output as JSON: {json_err}, using raw output")
                text = str(flow_output) if flow_output else text
        else:
            logger.warning(f"[WARN] Unexpected result format: {type(result)}")

        logger.info(f"[SUCCESS] Autobiography generation completed - autobiography_id={autobiography_id} user_id={user_id}")
        return AutobiographyGenerateResponseDto(
            title=str(title),
            autobiographical_text=str(text)
        )

    except json.JSONDecodeError as e:
        logger.error(f"[ERROR] JSON decode error autobiography_id={autobiography_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to parse the autobiography generation result.",
        )

    except ValidationError as e:
        logger.error(f"[ERROR] Validation error autobiography_id={autobiography_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"[ERROR] Unexpected error in autobiography generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post(
    "/cycle/init",
    summary="자서전 사이클 초기화",
    description="cycleId와 예상 챕터 수를 Redis에 저장합니다. 자서전 챕터 생성 요청을 일괄 보내기 전에 먼저 호출해야 합니다.",
    tags=["자서전 (Autobiography)"],
)
async def init_cycle(msg: CycleInitMessage):
    """사이클 초기화 엔드포인트.

    Backend 서버가 여러 챕터 생성을 시작하기 전에 cycleId와 총 챕터 수(expectedCount)를
    먼저 전송한다. AI 서버는 이를 Redis에 저장하고, 이후 generate 요청마다 완료 카운트를
    증가시켜 isLast 여부를 판단한다.
    """
    try:
        _session_manager.init_cycle(
            cycle_id=msg.cycleId,
            expected_count=msg.expectedCount,
            autobiography_id=msg.autobiographyId,
            user_id=msg.userId,
        )
        logger.info(f"[CYCLE_INIT] cycle_id={msg.cycleId} expected={msg.expectedCount}")
        return {"status": "ok", "cycleId": msg.cycleId}
    except Exception as e:
        logger.error(f"[CYCLE_INIT] Failed cycle_id={msg.cycleId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"사이클 초기화 실패: {str(e)}")
