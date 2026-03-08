import threading
import os
from logs import get_logger

logger = get_logger()


def start_all_consumers():
    """모든 SQS consumers를 백그라운드 스레드에서 시작."""

    def start_interview_summary_consumer():
        try:
            logger.info("[CONSUMER_MANAGER] Initializing interview summary consumer")
            from .interview_summary_consumer import InterviewSummaryConsumer
            InterviewSummaryConsumer().start_consuming()
        except Exception as e:
            logger.error(f"[CONSUMER_MANAGER] Interview summary consumer error: {e}", exc_info=True)

    def start_autobiography_consumer():
        try:
            logger.info("[CONSUMER_MANAGER] Initializing autobiography consumer")
            from .autobiography_consumer import AutobiographyConsumer
            AutobiographyConsumer().start_consuming()
        except Exception as e:
            logger.error(f"[CONSUMER_MANAGER] Autobiography consumer error: {e}", exc_info=True)

    def start_cycle_init_consumer():
        try:
            logger.info("[CONSUMER_MANAGER] Initializing cycle init consumer")
            from .cycle_init_consumer import CycleInitConsumer
            CycleInitConsumer().start_consuming()
        except Exception as e:
            logger.error(f"[CONSUMER_MANAGER] Cycle init consumer error: {e}", exc_info=True)

    required_env_vars = [
        "SQS_QUEUE_URL_AUTOBIOGRAPHY_TRIGGER",
        "SQS_QUEUE_URL_AUTOBIOGRAPHY_CYCLE_INIT",
        "SQS_QUEUE_URL_INTERVIEW_SUMMARY",
    ]
    if not all(os.environ.get(v) for v in required_env_vars):
        logger.warning("[CONSUMER_MANAGER] SQS Queue URL environment variables not set, skipping consumers")
        return

    logger.info("[CONSUMER_MANAGER] Starting all SQS consumers")

    threads = [
        threading.Thread(target=start_interview_summary_consumer, name="InterviewSummaryConsumer", daemon=True),
        threading.Thread(target=start_autobiography_consumer, name="AutobiographyConsumer", daemon=True),
        threading.Thread(target=start_cycle_init_consumer, name="CycleInitConsumer", daemon=True),
    ]

    for thread in threads:
        thread.start()
        logger.info(f"[CONSUMER_MANAGER] Started thread={thread.name}")

    logger.info("[CONSUMER_MANAGER] All SQS consumers started successfully")


start_all_consumers()
