import os
import logging
import json
import boto3
from openai import OpenAI
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
'''
autobiography는 자서전 요약이니까 이거랑 비슷하게 하되 interview id를 넣어서 하면 될듯? 
request 예시: 
{ "interview_id": 123,
  "conversation": [
    {
      "question": "자서전을 왜 만들고 싶으신가요?",
      "conversation": "아이들에게 제 이야기를 남기고 싶어서요."
    },
    {
      "question": "가장 기억에 남는 어린 시절의 장소는 어디인가요?",
      "conversation": "어릴 적에 살던 시골 집 뒤에 있는 작은 숲이요."
    }
  ]
}
result 예시:
{
  "interview_id": 123,
  "summary": "사용자는 자녀들에게 삶의 이야기를 남기고 싶어 자서전을 만들고자 한다. 어린 시절 시골 집 뒤 작은 숲에서 보낸 시간들이 특히 소중한 기억으로 남아 있다. 이러한 기억들을 바탕으로 가족에게 의미 있는 기록을 남기려는 마음이 드러난다."
}

'''

logger = logging.getLogger()
logger.setLevel(logging.INFO)
patch_all()




client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

def extract_qa_from_conversation(conversation):
    """대화에서 질의응답만 추출"""
    qa_pairs = []
    for item in conversation:
        if 'question' in item and 'conversation' in item:
            qa_pairs.append(f"Q: {item['question']}\nA: {item['conversation']}")
    return "\n\n".join(qa_pairs)

def lambda_handler(event, context):
    try:
        logger.info(f"Event: {json.dumps(event)}")
        
        interview_id = event.get('interview_id')
        conversation = event.get('conversation')
        
        if not interview_id or not conversation:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'interview_id and conversation are required'})
            }
        
        qa_text = extract_qa_from_conversation(conversation)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "당신은 인터뷰 내용을 요약하는 전문가입니다."},
                {"role": "user", "content": f"다음 대화록을 보고 내용을 줄글 3문장 이내로 요약하라.:\n\n{qa_text}"}
            ]
        )
        
        summary = response.choices[0].message.content
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'interview_id': interview_id,
                'summary': summary
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
