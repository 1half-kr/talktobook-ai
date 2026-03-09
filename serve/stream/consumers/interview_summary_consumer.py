import json
from pathlib import Path
import sys
from stream.sqs_client import get_sqs_client, get_queue_url, QueueUrl
from ..dto import InterviewSummaryResponsePayload
from interviews.interview_summary.dto.request import InterviewSummaryRequestDto
from logs import get_logger

# flow 경로 추가
current_dir = Path(__file__).parent.parent.parent.parent.parent
flows_dir = current_dir / "flows" / "interview_summary" / "standard" / "summarize_interview"
sys.path.insert(0, str(flows_dir))

from promptflow import load_flow

logger = get_logger()

_WAIT_TIME_SECONDS = 20
_VISIBILITY_TIMEOUT = 120  # 요약 처리 시간 여유


class InterviewSummaryConsumer:
    def __init__(self):
        logger.info("[SUMMARY_CONSUMER] Initializing")
        self.sqs = get_sqs_client()
        self.queue_url = get_queue_url(QueueUrl.INTERVIEW_SUMMARY)
        self.running = False
        self._setup_flow()
        logger.info(f"[SUMMARY_CONSUMER] Ready - queue={self.queue_url}")

    def _setup_flow(self):
        current_dir = Path(__file__).parent.parent.parent.parent
        flow_path = current_dir / "flows" / "interview_summary" / "standard" / "summarize_interview" / "flow.dag.yaml"
        logger.info(f"[SUMMARY_CONSUMER] Loading flow from {flow_path}")
        if not flow_path.exists():
            raise FileNotFoundError(f"Flow file not found: {flow_path}")
        self.flow = load_flow(str(flow_path))
        logger.info("[SUMMARY_CONSUMER] Flow loaded successfully")

    def start_consuming(self):
        self.running = True
        logger.info("[SUMMARY_CONSUMER] Starting polling loop")
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
                logger.error(f"[SUMMARY_CONSUMER] Polling error: {e}", exc_info=True)

    def _process(self, message: dict):
        receipt_handle = message["ReceiptHandle"]
        try:
            logger.info(f"[SUMMARY_CONSUMER] Message received - message_id={message['MessageId']}")

            raw_body = message["Body"]
            logger.debug(f"[SUMMARY_CONSUMER] Raw body repr={repr(raw_body[:200])}")
            payload_data = json.loads(raw_body)
            request_dto = InterviewSummaryRequestDto(**payload_data)

            logger.info(
                f"[SUMMARY_CONSUMER] Processing - interview_id={request_dto.interviewId} "
                f"user_id={request_dto.userId} conversations_count={len(request_dto.conversations)}"
            )

            result = self._run_flow(request_dto)

            from stream import publish_interview_summary_result
            publish_interview_summary_result(result)

            self._delete(receipt_handle)
            logger.info(f"[SUMMARY_CONSUMER] Message processed successfully - interview_id={request_dto.interviewId}")

        except json.JSONDecodeError as e:
            logger.error(f"[SUMMARY_CONSUMER] JSON decode error: {e}", exc_info=True)
            self._delete(receipt_handle)
        except Exception as e:
            logger.error(f"[SUMMARY_CONSUMER] Processing error: {e}", exc_info=True)
            # 삭제하지 않음 → DLQ로 이동

    def _run_flow(self, request_dto: InterviewSummaryRequestDto) -> InterviewSummaryResponsePayload:
        logger.info(f"[SUMMARY_CONSUMER] Executing flow - interview_id={request_dto.interviewId}")
        result = self.flow(conversation=[conv.model_dump() for conv in request_dto.conversations])
        logger.info(f"[SUMMARY_CONSUMER] Flow execution complete - interview_id={request_dto.interviewId}")

        summary = result.get("summary", "")
        if hasattr(summary, "__iter__") and not isinstance(summary, str):
            summary = "".join(summary)

        logger.info(f"[SUMMARY_CONSUMER] Summary generated - interview_id={request_dto.interviewId} summary_length={len(str(summary))}")
        return InterviewSummaryResponsePayload(
            interviewId=request_dto.interviewId,
            userId=request_dto.userId,
            summary=str(summary),
        )

    def _delete(self, receipt_handle: str):
        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)

    def stop(self):
        self.running = False
        logger.info("[SUMMARY_CONSUMER] Stopped")


if __name__ == "__main__":
    consumer = InterviewSummaryConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.stop()
