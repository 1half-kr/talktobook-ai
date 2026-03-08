import json
import os
from logs import get_logger
from .dto import InterviewPayload, CategoriesPayload, GeneratedAutobiographyPayload, InterviewSummaryResponsePayload
from .sqs_client import get_sqs_client, get_queue_url, QueueUrl

logger = get_logger()


def _send_message(queue_url_env_key: str, body: str, log_prefix: str):
    queue_url = get_queue_url(queue_url_env_key)
    sqs = get_sqs_client()
    sqs.send_message(QueueUrl=queue_url, MessageBody=body)
    logger.info(f"[{log_prefix}] Published to {queue_url_env_key}")


def publish_persistence_message(payload: InterviewPayload):
    """인터뷰 응답을 SpringBoot ai.persistence 큐로 전송."""
    try:
        logger.info(f"[PUBLISH_PERSISTENCE] Starting - autobiography_id={payload.autobiographyId} user_id={payload.userId}")
        _send_message(QueueUrl.AI_PERSISTENCE, payload.model_dump_json(), "PUBLISH_PERSISTENCE")
        logger.info(f"[PUBLISH_PERSISTENCE] Success - autobiography_id={payload.autobiographyId}")
    except Exception as e:
        logger.error(f"[PUBLISH_PERSISTENCE] Failed - autobiography_id={payload.autobiographyId}: {e}", exc_info=True)
        raise


def publish_categories_message(payload: CategoriesPayload):
    """카테고리/메타데이터 변경사항을 SpringBoot interview.meta 큐로 전송."""
    try:
        logger.info(f"[PUBLISH_CATEGORIES] Starting - autobiography_id={payload.autobiographyId} category_id={payload.categoryId} theme_id={payload.themeId}")
        logger.info(f"[PUBLISH_CATEGORIES_DEBUG] chunks={payload.chunks}")
        logger.info(f"[PUBLISH_CATEGORIES_DEBUG] materials={payload.materials}")
        body = payload.model_dump_json()
        logger.info(f"[PUBLISH_CATEGORIES_DEBUG] body={body}")
        _send_message(QueueUrl.INTERVIEW_META, body, "PUBLISH_CATEGORIES")
        logger.info(f"[PUBLISH_CATEGORIES] Success - autobiography_id={payload.autobiographyId} category_id={payload.categoryId}")
    except Exception as e:
        logger.error(f"[PUBLISH_CATEGORIES] Failed - autobiography_id={payload.autobiographyId}: {e}", exc_info=True)
        raise


def publish_generated_autobiography(payload: GeneratedAutobiographyPayload):
    """생성된 자서전 chapter를 SpringBoot autobiography.trigger.result 큐로 전송."""
    try:
        logger.info(f"[PUBLISH_AUTOBIOGRAPHY] Starting - autobiography_id={payload.autobiographyId} user_id={payload.userId} cycle_id={payload.cycleId} step={payload.step}")
        _send_message(QueueUrl.AUTOBIOGRAPHY_RESULT, payload.model_dump_json(), "PUBLISH_AUTOBIOGRAPHY")
        logger.info(f"[PUBLISH_AUTOBIOGRAPHY] Success - autobiography_id={payload.autobiographyId}")
    except Exception as e:
        logger.error(f"[PUBLISH_AUTOBIOGRAPHY] Failed - autobiography_id={payload.autobiographyId}: {e}", exc_info=True)
        raise


def publish_interview_summary_result(payload: InterviewSummaryResponsePayload):
    """인터뷰 요약 결과를 SpringBoot interview.summary.result 큐로 전송."""
    try:
        logger.info(f"[PUBLISH_SUMMARY] Starting - interview_id={payload.interviewId} user_id={payload.userId}")
        _send_message(QueueUrl.INTERVIEW_SUMMARY_RESULT, payload.model_dump_json(), "PUBLISH_SUMMARY")
        logger.info(f"[PUBLISH_SUMMARY] Success - interview_id={payload.interviewId}")
    except Exception as e:
        logger.error(f"[PUBLISH_SUMMARY] Failed - interview_id={payload.interviewId}: {e}", exc_info=True)
        raise


def publish_cycle_merge(payload: GeneratedAutobiographyPayload):
    """모든 챕터 완료(isLast=True) 시 SpringBoot autobiography.cycle.merge 큐로 완료 신호 전송."""
    try:
        logger.info(
            f"[PUBLISH_CYCLE_MERGE] Starting - cycle_id={payload.cycleId} "
            f"autobiography_id={payload.autobiographyId} user_id={payload.userId}"
        )
        merge_message = {
            "cycleId": payload.cycleId,
            "step": payload.step,
            "autobiographyId": payload.autobiographyId,
            "userId": payload.userId,
            "action": "merge",
            "title": payload.title,
            "content": payload.content,
        }
        _send_message(QueueUrl.AUTOBIOGRAPHY_CYCLE_MERGE, json.dumps(merge_message), "PUBLISH_CYCLE_MERGE")
        logger.info(f"[PUBLISH_CYCLE_MERGE] Success - cycle_id={payload.cycleId}")
    except Exception as e:
        logger.error(f"[PUBLISH_CYCLE_MERGE] Failed - cycle_id={payload.cycleId}: {e}", exc_info=True)
        raise
