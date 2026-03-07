import json
import os
import pika
from ..dto import InterviewAnswersPayload
from autobiographies.generate_autobiography.router import generate_autobiography_fn
from logs import get_logger

logger = get_logger()


class AutobiographyConsumer:
    def __init__(self):
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Initializing autobiography consumer")
        self.setup_connection()
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Initialization complete")

    def setup_connection(self):
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT"))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")

        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Connecting to RabbitMQ - host={rabbitmq_host} port={rabbitmq_port}")

        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials,
            )
        )
        self.channel = self.connection.channel()
        logger.info("[AUTOBIOGRAPHY_CONSUMER] RabbitMQ connection established")

    def start_consuming(self):
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Starting to consume from queue=autobiography.trigger.queue")
        self.channel.basic_consume(
            queue='autobiography.trigger.queue',
            on_message_callback=self.on_message,
            auto_ack=False,
        )
        self.channel.start_consuming()

    def on_message(self, channel, method, properties, body):
        try:
            logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Message received - delivery_tag={method.delivery_tag}")

            payload_data = json.loads(body)

            if payload_data.get("action") == "merge":
                logger.warning("[AUTOBIOGRAPHY_CONSUMER] Merge message received, rejecting")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            cycle_id = payload_data.get("cycleId")
            step = payload_data.get("step", 1)

            if not cycle_id:
                logger.warning("[AUTOBIOGRAPHY_CONSUMER] Message rejected - cycleId missing")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            payload = InterviewAnswersPayload(**payload_data)
            logger.info(
                f"[AUTOBIOGRAPHY_CONSUMER] Processing - autobiography_id={payload.autobiographyId} "
                f"user_id={payload.userId} cycle_id={cycle_id} step={step} answers_count={len(payload.answers)}"
            )

            # generate_autobiography_fn: 자서전 생성 + cycle 완료 여부(isLast) 판단까지 수행
            result = generate_autobiography_fn(payload)

            from stream import publish_generated_autobiography, publish_cycle_merge
            publish_generated_autobiography(result)

            # 모든 챕터 생성 완료 시 Spring Boot merge consumer로 신호 전송
            if result.isLast:
                logger.info(
                    f"[AUTOBIOGRAPHY_CONSUMER] All chapters done, publishing merge signal - "
                    f"cycle_id={cycle_id} autobiography_id={payload.autobiographyId}"
                )
                publish_cycle_merge(result)

            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(
                f"[AUTOBIOGRAPHY_CONSUMER] Message processed successfully - "
                f"autobiography_id={payload.autobiographyId} cycle_id={cycle_id} is_last={result.isLast}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] JSON decode error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] Processing error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def close(self):
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Closing connection")
        self.connection.close()


if __name__ == "__main__":
    consumer = AutobiographyConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.close()