import json
import os
import sys
from pathlib import Path
import pika
from promptflow.core import Flow
from ..dto import InterviewAnswersPayload, GeneratedAutobiographyPayload
from autobiographies.generate_autobiography.dto.request import (
    AutobiographyGenerateRequestDto, 
    UserInfoDto, 
    AutobiographyInfoDto, 
    InterviewContentDto
)
from constants import ConversationType
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
                credentials=credentials
            )
        )
        self.channel = self.connection.channel()
        logger.info("[AUTOBIOGRAPHY_CONSUMER] RabbitMQ connection established")
    
    def start_consuming(self):
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Starting to consume from queue=autobiography.trigger.queue")
        self.channel.basic_consume(
            queue='autobiography.trigger.queue',
            on_message_callback=self.on_message,
            auto_ack=False
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
            logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Processing - autobiography_id={payload.autobiographyId} user_id={payload.userId} cycle_id={cycle_id} step={step} answers_count={len(payload.answers)}")
            
            result = self.consume_interview_answers(payload)
            
            from stream import publish_result_to_aggregator
            publish_result_to_aggregator(
                cycle_id, 
                step, 
                payload.autobiographyId, 
                payload.userId,
                {"title": result.title, "content": result.content}
            )
            
            from stream import publish_generated_autobiography
            result.cycleId = cycle_id
            result.step = step
            publish_generated_autobiography(result)
            
            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Message processed successfully - autobiography_id={payload.autobiographyId} cycle_id={cycle_id}")
            
        except json.JSONDecodeError as e:
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] JSON decode error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] Processing error: {e}", exc_info=True)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def consume_interview_answers(self, payload: InterviewAnswersPayload):
        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Starting generation - autobiography_id={payload.autobiographyId} user_id={payload.userId}")
        
        user_info = UserInfoDto(
            gender=payload.userInfo.gender,
            occupation=payload.userInfo.occupation,
            age_group=payload.userInfo.ageGroup
        )
        
        autobiography_info = AutobiographyInfoDto(
            theme=payload.autobiographyInfo.theme,
            reason=payload.autobiographyInfo.reason,
            category=payload.autobiographyInfo.category
        )
        
        interviews = [
            InterviewContentDto(
                content=answer.content,
                conversation_type=ConversationType(answer.conversationType)
            )
            for answer in payload.answers
        ]
        
        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Data converted - interviews_count={len(interviews)} theme={autobiography_info.theme} category={autobiography_info.category}")
        
        current_file = Path(__file__).resolve()
        serve_dir = current_file.parent.parent.parent
        project_root = serve_dir.parent
        flow_path = project_root / "flows" / "autobiographies" / "standard" / "generate_autobiography" / "flow.dag.yaml"
        
        if not flow_path.exists():
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] Flow file not found at {flow_path}")
            raise FileNotFoundError(f"Flow file not found at: {flow_path}")
        
        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Executing flow - autobiography_id={payload.autobiographyId}")
        flow = Flow.load(str(flow_path))
        result = flow(
            user_info=user_info.dict(),
            autobiography_info=autobiography_info.dict(),
            interviews=[interview.dict() for interview in interviews],
            autobiography_id=payload.autobiographyId
        )
        
        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Flow execution complete - autobiography_id={payload.autobiographyId}")
        
        title = f"{autobiography_info.theme} - {autobiography_info.category}에 대한 나의 이야기"
        text = "자서전 생성 완료"
        
        try:
            flow_output = result.get("result") if isinstance(result, dict) else result
            
            if hasattr(flow_output, '__iter__') and not isinstance(flow_output, (str, dict)):
                flow_content = ''.join(str(item) for item in flow_output)
            else:
                flow_content = str(flow_output)
            
            try:
                parsed = json.loads(flow_content)
                
                if isinstance(parsed, dict):
                    title = parsed.get("title", title)
                    text = parsed.get("autobiographical_text", text)
                    logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Result parsed - title_length={len(title)} text_length={len(text)}")
                else:
                    text = flow_content
                    logger.warning("[AUTOBIOGRAPHY_CONSUMER] Parsed output is not dict, using as text")
            except json.JSONDecodeError as json_error:
                logger.error(f"[AUTOBIOGRAPHY_CONSUMER] JSON parsing failed: {json_error}")
                text = flow_content
                
        except Exception as parse_error:
            text = str(result) if result else text
            logger.error(f"[AUTOBIOGRAPHY_CONSUMER] Result processing failed: {parse_error}", exc_info=True)
        
        final_result = GeneratedAutobiographyPayload(
            autobiographyId=payload.autobiographyId,
            userId=payload.userId,
            title=str(title),
            content=str(text)
        )
        
        logger.info(f"[AUTOBIOGRAPHY_CONSUMER] Generation completed - autobiography_id={payload.autobiographyId} user_id={payload.userId}")
        return final_result
    
    def close(self):
        logger.info("[AUTOBIOGRAPHY_CONSUMER] Closing connection")
        self.connection.close()

if __name__ == "__main__":
    consumer = AutobiographyConsumer()
    try:
        consumer.start_consuming()
    except KeyboardInterrupt:
        consumer.close()