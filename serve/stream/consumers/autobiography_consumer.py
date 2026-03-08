import json
from stream.sqs_client import get_sqs_client, get_queue_url, QueueUrl
from ..dto import InterviewAnswersPayload
from autobiographies.generate_autobiography.router import generate_autobiography_fn
from logs import get_logger

logger = get_logger()

_WAIT_TIME_SECONDS = 20   # long polling
_VISIBILITY_TIMEOUT = 300  # 5분 (AI 생성 처리 시간 여유)


class AutobiographyConsumer:
    def __init__(self):
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Initializing")
        self.sqs = get_sqs_client()
        self.queue_url = get_queue_url(QueueUrl.AUTOBIOGRAPHY_TRIGGER)
        self.running = False
        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Ready - queue={self.queue_url}")

    def start_consuming(self):
        self.running = True
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Starting polling loop")
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
                logger.error(f"[AUTOBIOGRAPHY_CONSUMER] Polling error: {e}", exc_info=True)

    def _process(self, message: dict):
        receipt_handle = message["ReceiptHandle"]
        try:
            logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Message received - message_id={message['MessageId']}")

            payload_data = json.loads(message["Body"])

            if payload_data.get("action") == "merge":
                logger.warning("[AUTOBIOGRAPHY_CONSUMER] Merge message received, discarding")
                self._delete(receipt_handle)
                return

            cycle_id = payload_data.get("cycleId")
            step = payload_data.get("step", 1)

            if not cycle_id:
                logger.warning("[AUTOBIOGRAPHY_CONSUMER] Message rejected - cycleId missing")
                # 삭제하지 않으면 visibility timeout 후 DLQ로 이동하므로 명시적 삭제
                self._delete(receipt_handle)
                return

            payload = InterviewAnswersPayload(**payload_data)
            logger.info(
                f"[AUTOBIOGRAPHY_CONSUMER] Processing - autobiography_id={payload.autobiographyId} "
                f"user_id={payload.userId} cycle_id={cycle_id} step={step} answers_count={len(payload.answers)}"
            )

            result = generate_autobiography_fn(payload)

            from stream import publish_generated_autobiography, publish_cycle_merge
            publish_generated_autobiography(result)

            if result.isLast:
                logger.info(
                    f"[AUTOBIOGRAPHY_CONSUMER] All chapters done, publishing merge signal - "
                    f"cycle_id={cycle_id} autobiography_id={payload.autobiographyId}"
                )
                publish_cycle_merge(result)

            self._delete(receipt_handle)
            logger.info(
                f"[AUTOBIOGRAPHY_CONSUMER] Message processed successfully - "
                f"autobiography_id={payload.autobiographyId} cycle_id={cycle_id} is_last={result.isLast}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] JSON decode error: {e}", exc_info=True)
            # 파싱 불가 메시지는 즉시 삭제 (DLQ 불필요)
            self._delete(receipt_handle)
        except Exception as e:
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] Processing error: {e}", exc_info=True)
            # 삭제하지 않음 → visibility timeout 만료 후 DLQ로 이동

    def _delete(self, receipt_handle: str):
        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)

    def stop(self):
        self.running = False
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Stopped")


if __name__ == "__main__":
    consumer = AutobiographyConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.stop()
