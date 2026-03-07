"""AWS 클라이언트 - 서버 측에서만 사용"""
import os
import boto3
from botocore.exceptions import ClientError

class AWSVoiceClient:
    def __init__(self):
        # Profile 사용 시
        profile_name = os.getenv('AWS_PROFILE')
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            self.polly_client = session.client('polly')
            self.transcribe_client = session.client('transcribe')
        else:
            # 환경 변수 직접 사용
            self.polly_client = boto3.client(
                'polly',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
            )
            self.transcribe_client = boto3.client(
                'transcribe',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
            )
    
    def text_to_speech(self, text: str, voice_id: str = "Seoyeon") -> bytes:
        """TTS - 텍스트를 음성으로 변환"""
        try:
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine='neural'
            )
            return response['AudioStream'].read()
        except ClientError as e:
            print(f"[ERROR] TTS 실패: {e}")
            raise
    
    def get_presigned_url(self, text: str, voice_id: str = "Seoyeon") -> str:
        """TTS - Presigned URL 생성 (클라이언트가 직접 다운로드)"""
        try:
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine='neural'
            )
            # S3에 업로드 후 presigned URL 반환하는 로직 추가 가능
            return response['AudioStream'].read()
        except ClientError as e:
            print(f"[ERROR] Presigned URL 생성 실패: {e}")
            raise
