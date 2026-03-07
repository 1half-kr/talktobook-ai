# ai_mq_producer.py
import json
import pika
import os
from logs import get_logger
from .dto import InterviewPayload, CategoriesPayload, GeneratedAutobiographyPayload, InterviewSummaryResponsePayload

logger = get_logger()


def publish_persistence_message(payload: InterviewPayload):
    """
    interview에 대한 응답 메시지를 publish하는 함수.
    """
    try:
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT"))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")
        
        logger.info(f"[PUBLISH_PERSISTENCE] Starting - autobiography_id={payload.autobiographyId} user_id={payload.userId}")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials
            )
        )
        channel = connection.channel()
        
        body = payload.model_dump_json()
        logger.info(f"[PUBLISH_PERSISTENCE] Publishing to exchange=ai.request.exchange routing_key=ai.persistence")

        channel.basic_publish(
            exchange='ai.request.exchange',
            routing_key='ai.persistence',
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2
            )
        )

        connection.close()
        logger.info(f"[PUBLISH_PERSISTENCE] Success - autobiography_id={payload.autobiographyId}")
    except Exception as e:
        logger.error(f"[PUBLISH_PERSISTENCE] Failed - autobiography_id={payload.autobiographyId}: {e}", exc_info=True)
        raise
    
def publish_categories_message(payload: CategoriesPayload):
    """
    autobiography에 대한 categories, chunks, materials 변경 사항 메시지를 publish하는 함수.
    """
    try:
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", 5672))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")
        
        logger.info(f"[PUBLISH_CATEGORIES] Starting - autobiography_id={payload.autobiographyId} category_id={payload.categoryId} theme_id={payload.themeId}")
        logger.info(f"[PUBLISH_CATEGORIES_DEBUG] chunks={payload.chunks}")
        logger.info(f"[PUBLISH_CATEGORIES_DEBUG] materials={payload.materials}")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials
            )
        )
        channel = connection.channel()

        body = payload.model_dump_json()
        logger.info(f"[PUBLISH_CATEGORIES] Publishing to exchange=interview.meta.exchange routing_key=interview.meta")
        logger.info(f"[PUBLISH_CATEGORIES_DEBUG] body={body}")
        
        channel.basic_publish(
            exchange='interview.meta.exchange',
            routing_key='interview.meta',
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2
            )
        )
        
        connection.close()
        logger.info(f"[PUBLISH_CATEGORIES] Success - autobiography_id={payload.autobiographyId} category_id={payload.categoryId}")
    except Exception as e:
        logger.error(f"[PUBLISH_CATEGORIES] Failed - autobiography_id={payload.autobiographyId}: {e}", exc_info=True)
        raise

def publish_generated_autobiography(payload: GeneratedAutobiographyPayload):
    """
    생성된 자서전 결과를 publish하는 함수.
    """
    try:
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", 5672))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")
        
        logger.info(f"[PUBLISH_AUTOBIOGRAPHY] Starting - autobiography_id={payload.autobiographyId} user_id={payload.userId} cycle_id={payload.cycleId} step={payload.step}")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials
            )
        )
        channel = connection.channel()
        
        body = payload.model_dump_json()
        logger.info(f"[PUBLISH_AUTOBIOGRAPHY] Publishing to exchange=autobiography.trigger.exchange routing_key=autobiography.trigger.result")
        
        channel.basic_publish(
            exchange='autobiography.trigger.exchange',
            routing_key='autobiography.trigger.result',
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2
            )
        )
        
        connection.close()
        logger.info(f"[PUBLISH_AUTOBIOGRAPHY] Success - autobiography_id={payload.autobiographyId}")
    except Exception as e:
        logger.error(f"[PUBLISH_AUTOBIOGRAPHY] Failed - autobiography_id={payload.autobiographyId}: {e}", exc_info=True)
        raise

def publish_result_to_aggregator(cycle_id: str, step: int, autobiography_id: int, user_id: int, result_data: dict):
    """
    Aggregator로 작업 완료 결과를 전송하는 함수.
    """
    try:
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", 5672))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")
        
        logger.info(f"[PUBLISH_AGGREGATOR] Starting - cycle_id={cycle_id} step={step} autobiography_id={autobiography_id} user_id={user_id}")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials
            )
        )
        channel = connection.channel()
        
        result_message = {
            "cycleId": cycle_id,
            "step": step,
            "autobiographyId": autobiography_id,
            "userId": user_id,
            "result": result_data,
            "status": "completed"
        }
        
        logger.info(f"[PUBLISH_AGGREGATOR] Publishing to exchange=autobiography.trigger.exchange routing_key=autobiography.trigger.cycle.result")
        
        channel.basic_publish(
            exchange='autobiography.trigger.exchange',
            routing_key='autobiography.trigger.cycle.result',
            body=json.dumps(result_message),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                headers={'cycle_id': cycle_id}
            )
        )
        
        connection.close()
        logger.info(f"[PUBLISH_AGGREGATOR] Success - cycle_id={cycle_id} step={step}")
    except Exception as e:
        logger.error(f"[PUBLISH_AGGREGATOR] Failed - cycle_id={cycle_id} step={step}: {e}", exc_info=True)
        raise

def publish_interview_summary_result(payload: InterviewSummaryResponsePayload):
    """
    인터뷰 요약 결과를 publish하는 함수.
    """
    try:
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", 5672))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")
        
        logger.info(f"[PUBLISH_SUMMARY] Starting - interview_id={payload.interviewId} user_id={payload.userId}")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials
            )
        )
        channel = connection.channel()
        
        body = payload.model_dump_json()
        logger.info(f"[PUBLISH_SUMMARY] Publishing to exchange=interview.summary.exchange routing_key=interview.summary.result")
        
        channel.basic_publish(
            exchange='interview.summary.exchange',
            routing_key='interview.summary.result',
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2
            )
        )
        
        connection.close()
        logger.info(f"[PUBLISH_SUMMARY] Success - interview_id={payload.interviewId}")
    except Exception as e:
        logger.error(f"[PUBLISH_SUMMARY] Failed - interview_id={payload.interviewId}: {e}", exc_info=True)
        raise