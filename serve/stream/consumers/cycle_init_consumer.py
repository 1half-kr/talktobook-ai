import json
import os
import pika
from ..dto import CycleInitMessage
from session_manager import SessionManager
from logs import get_logger

logger = get_logger()

_session_manager = SessionManager()


class CycleInitConsumer:
    """autobiography.trigger.cycle.init.queue 소비.

    Spring Boot CycleInitPublisher가 발행하는 CycleInitMessage를 수신하여
    Redis에 cycle 정보를 저장한다.
    """

    def __init__(self):
        logger.info("[CYCLE_INIT_CONSUMER] Initializing")
        self.setup_connection()
        logger.info("[CYCLE_INIT_CONSUMER] Initialization complete")

    def setup_connection(self):
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT"))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")

        logger.info(f"[CYCLE_INIT_CONSUMER] Connecting to RabbitMQ - host={rabbitmq_host} port={rabbitmq_port}")

        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials,
            )
        )
        self.channel = self.connection.channel()
        logger.info("[CYCLE_INIT_CONSUMER] RabbitMQ connection established")

    def start_consuming(self):
        logger.info("[CYCLE_INIT_CONSUMER] Starting to consume from queue=autobiography.trigger.cycle.init.queue")
        self.channel.basic_consume(
            queue='autobiography.trigger.cycle.init.queue',
            on_message_callback=self.on_message,
            auto_ack=False,
        )
        self.channel.start_consuming()

    def on_message(self, channel, method, properties, body):
        try:
            logger.info(f"[CYCLE_INIT_CONSUMER] Message received - delivery_tag={method.delivery_tag}")

            payload_data = json.loads(body)
            msg = CycleInitMessage(**payload_data)

            logger.info(
                f"[CYCLE_INIT_CONSUMER] Processing - cycle_id={msg.cycleId} "
                f"expected={msg.expectedCount} autobiography_id={msg.autobiographyId}"
            )

            _session_manager.init_cycle(
                cycle_id=msg.cycleId,
                expected_count=msg.expectedCount,
                autobiography_id=msg.autobiographyId,
                user_id=msg.userId,
            )

            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"[CYCLE_INIT_CONSUMER] Cycle initialized - cycle_id={msg.cycleId}")

        except json.JSONDecodeError as e:
            logger.error(f"[CYCLE_INIT_CONSUMER] JSON decode error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"[CYCLE_INIT_CONSUMER] Processing error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def close(self):
        logger.info("[CYCLE_INIT_CONSUMER] Closing connection")
        self.connection.close()


if __name__ == "__main__":
    consumer = CycleInitConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.close()
