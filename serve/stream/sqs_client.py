import os
import boto3
from logs import get_logger

logger = get_logger()

_sqs_client = None


def get_sqs_client():
    """boto3 SQS 클라이언트 싱글톤 반환."""
    global _sqs_client
    if _sqs_client is None:
        region = os.environ.get("AWS_REGION", "ap-northeast-2")
        _sqs_client = boto3.client("sqs", region_name=region)
        logger.info(f"[SQS] Client initialized - region={region}")
    return _sqs_client


# 큐 URL 환경변수 키 상수
class QueueUrl:
    AUTOBIOGRAPHY_TRIGGER = "SQS_QUEUE_URL_AUTOBIOGRAPHY_TRIGGER"
    AUTOBIOGRAPHY_CYCLE_INIT = "SQS_QUEUE_URL_AUTOBIOGRAPHY_CYCLE_INIT"
    AUTOBIOGRAPHY_RESULT = "SQS_QUEUE_URL_AUTOBIOGRAPHY_RESULT"
    AUTOBIOGRAPHY_CYCLE_MERGE = "SQS_QUEUE_URL_AUTOBIOGRAPHY_CYCLE_MERGE"
    INTERVIEW_SUMMARY = "SQS_QUEUE_URL_INTERVIEW_SUMMARY"
    INTERVIEW_SUMMARY_RESULT = "SQS_QUEUE_URL_INTERVIEW_SUMMARY_RESULT"
    INTERVIEW_META = "SQS_QUEUE_URL_INTERVIEW_META"
    AI_PERSISTENCE = "SQS_QUEUE_URL_AI_PERSISTENCE"


def get_queue_url(env_key: str) -> str:
    url = os.environ.get(env_key)
    if not url:
        raise EnvironmentError(f"SQS Queue URL not set: {env_key}")
    return url
