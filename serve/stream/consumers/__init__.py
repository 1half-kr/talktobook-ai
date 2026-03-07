import threading
import os
from logs import get_logger

logger = get_logger()

def start_all_consumers():
    """모든 RabbitMQ consumers를 백그라운드에서 시작"""

    def start_interview_summary_consumer():
        try:
            logger.info("[CONSUMER_MANAGER] Initializing interview summary consumer")
            from .interview_summary_consumer import InterviewSummaryConsumer
            consumer = InterviewSummaryConsumer()
            consumer.start_consuming()
        except Exception as e:
            logger.error(f"[CONSUMER_MANAGER] Interview summary consumer error: {e}", exc_info=True)

    def start_autobiography_consumer():
        try:
            logger.info("[CONSUMER_MANAGER] Initializing autobiography consumer")
            from .autobiography_consumer import AutobiographyConsumer
            consumer = AutobiographyConsumer()
            consumer.start_consuming()
        except Exception as e:
            logger.error(f"[CONSUMER_MANAGER] Autobiography consumer error: {e}", exc_info=True)

    if not all([
        os.environ.get("RABBITMQ_HOST"),
        os.environ.get("RABBITMQ_USER"),
        os.environ.get("RABBITMQ_PASSWORD")
    ]):
        logger.warning("[CONSUMER_MANAGER] RabbitMQ environment variables not set, skipping consumers")
        return

    logger.info("[CONSUMER_MANAGER] Starting all RabbitMQ consumers")
    
    threads = []
    
    interview_summary_thread = threading.Thread(
        target=start_interview_summary_consumer,
        name="InterviewSummaryConsumer", 
        daemon=True
    )
    
    autobiography_thread = threading.Thread(
        target=start_autobiography_consumer,
        name="AutobiographyConsumer",
        daemon=True
    )
    
    threads.extend([interview_summary_thread, autobiography_thread])
    
    for thread in threads:
        thread.start()
        logger.info(f"[CONSUMER_MANAGER] Started thread={thread.name}")
    
    logger.info("[CONSUMER_MANAGER] All RabbitMQ consumers started successfully")

start_all_consumers()
