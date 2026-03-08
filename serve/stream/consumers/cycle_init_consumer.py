import json
from stream.sqs_client import get_sqs_client, get_queue_url, QueueUrl
from ..dto import CycleInitMessage
from session_manager import SessionManager
from logs import get_logger

logger = get_logger()

_session_manager = SessionManager()

_WAIT_TIME_SECONDS = 20
_VISIBILITY_TIMEOUT = 30


class CycleInitConsumer:
    """autobiography.cycle.init 큐 소비.

    SpringBoot CycleInitPublisher가 발행하는 CycleInitMessage를 수신하여
    Redis에 cycle 정보를 저장한다.
    """

    def __init__(self):
        logger.info("[CYCLE_INIT_CONSUMER] Initializing")
        self.sqs = get_sqs_client()
        self.queue_url = get_queue_url(QueueUrl.AUTOBIOGRAPHY_CYCLE_INIT)
        self.running = False
        logger.info(f"[CYCLE_INIT_CONSUMER] Ready - queue={self.queue_url}")

    def start_consuming(self):
        self.running = True
        logger.info("[CYCLE_INIT_CONSUMER] Starting polling loop")
        while self.running:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=_WAIT_TIME_SECONDS,
                    VisibilityTimeout=_VISIBILITY_TIMEOUT,
                )
                for message in response.get("Messages", []):
                    self._process(message)
            except Exception as e:
                logger.error(f"[CYCLE_INIT_CONSUMER] Polling error: {e}", exc_info=True)

    def _process(self, message: dict):
        receipt_handle = message["ReceiptHandle"]
        try:
            logger.info(f"[CYCLE_INIT_CONSUMER] Message received - message_id={message['MessageId']}")

            payload_data = json.loads(message["Body"])
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

            self._delete(receipt_handle)
            logger.info(f"[CYCLE_INIT_CONSUMER] Cycle initialized - cycle_id={msg.cycleId}")

        except json.JSONDecodeError as e:
            logger.error(f"[CYCLE_INIT_CONSUMER] JSON decode error: {e}", exc_info=True)
            self._delete(receipt_handle)
        except Exception as e:
            logger.error(f"[CYCLE_INIT_CONSUMER] Processing error: {e}", exc_info=True)
            # 삭제하지 않음 → DLQ로 이동

    def _delete(self, receipt_handle: str):
        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)

    def stop(self):
        self.running = False
        logger.info("[CYCLE_INIT_CONSUMER] Stopped")


if __name__ == "__main__":
    consumer = CycleInitConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.stop()
