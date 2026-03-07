import json
import os
import pika
from pathlib import Path
import sys
from ..dto import InterviewSummaryResponsePayload
from interviews.interview_summary.dto.request import InterviewSummaryRequestDto, ConversationDto
from logs import get_logger

# flow 경로 추가
current_dir = Path(__file__).parent.parent.parent.parent.parent
flows_dir = current_dir / "flows" / "interview_summary" / "standard" / "summarize_interview"
sys.path.insert(0, str(flows_dir))

from promptflow import load_flow

logger = get_logger()

class InterviewSummaryConsumer:
    def __init__(self):
        logger.info("[SUMMARY_CONSUMER] Initializing interview summary consumer")
        self.setup_connection()
        self.setup_flow()
        logger.info("[SUMMARY_CONSUMER] Initialization complete")
    
    def setup_connection(self):
        rabbitmq_host = os.environ.get("RABBITMQ_HOST")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT"))
        rabbitmq_user = os.environ.get("RABBITMQ_USER")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD")
        
        logger.info(f"[SUMMARY_CONSUMER] Connecting to RabbitMQ - host={rabbitmq_host} port={rabbitmq_port}")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                credentials=credentials
            )
        )
        self.channel = self.connection.channel()
        logger.info("[SUMMARY_CONSUMER] RabbitMQ connection established")
    
    def setup_flow(self):
        current_dir = Path(__file__).parent.parent.parent.parent
        flow_path = current_dir / "flows" / "interview_summary" / "standard" / "summarize_interview" / "flow.dag.yaml"
        
        logger.info(f"[SUMMARY_CONSUMER] Loading flow from {flow_path}")
        
        if not flow_path.exists():
            logger.error(f"[SUMMARY_CONSUMER] Flow file not found at {flow_path}")
            raise FileNotFoundError(f"Flow file not found: {flow_path}")
        
        self.flow = load_flow(str(flow_path))
        logger.info("[SUMMARY_CONSUMER] Flow loaded successfully")
    
    def start_consuming(self):
        logger.info("[SUMMARY_CONSUMER] Starting to consume from queue=interview.summary.queue")
        self.channel.basic_consume(
            queue='interview.summary.queue',
            on_message_callback=self.on_message,
            auto_ack=False
        )
        self.channel.start_consuming()
    
    def on_message(self, channel, method, properties, body):
        try:
            logger.info(f"[SUMMARY_CONSUMER] Message received - delivery_tag={method.delivery_tag}")
            
            payload_data = json.loads(body)
            request_dto = InterviewSummaryRequestDto(**payload_data)
            
            logger.info(f"[SUMMARY_CONSUMER] Processing - interview_id={request_dto.interviewId} user_id={request_dto.userId} conversations_count={len(request_dto.conversations)}")
            
            result = self.consume_interview_summary(request_dto)
            
            from stream import publish_interview_summary_result
            publish_interview_summary_result(result)
            
            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"[SUMMARY_CONSUMER] Message processed successfully - interview_id={request_dto.interviewId}")
            
        except json.JSONDecodeError as e:
            logger.error(f"[SUMMARY_CONSUMER] JSON decode error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"[SUMMARY_CONSUMER] Processing error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def consume_interview_summary(self, request_dto: InterviewSummaryRequestDto):
        try:
            logger.info(f"[SUMMARY_CONSUMER] Executing flow - interview_id={request_dto.interviewId}")
            
            result = self.flow(
                conversation=[conv.model_dump() for conv in request_dto.conversations]
            )
            
            logger.info(f"[SUMMARY_CONSUMER] Flow execution complete - interview_id={request_dto.interviewId}")
            
            summary = result.get("summary", "")
            
            if hasattr(summary, '__iter__') and not isinstance(summary, str):
                summary = ''.join(summary)
            
            logger.info(f"[SUMMARY_CONSUMER] Summary generated - interview_id={request_dto.interviewId} summary_length={len(str(summary))}")
            
            return InterviewSummaryResponsePayload(
                interviewId=request_dto.interviewId,
                userId=request_dto.userId,
                summary=str(summary)
            )
            
        except Exception as e:
            logger.error(f"[SUMMARY_CONSUMER] Flow execution failed - interview_id={request_dto.interviewId}: {e}", exc_info=True)
            raise
    
    def close(self):
        logger.info("[SUMMARY_CONSUMER] Closing connection")
        self.connection.close()

if __name__ == "__main__":
    consumer = InterviewSummaryConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.close()
