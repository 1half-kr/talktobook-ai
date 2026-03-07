"""실시간 STT - AWS Transcribe Streaming"""
import asyncio
import os
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

class StreamHandler(TranscriptResultStreamHandler):
    def __init__(self, transcript_result_stream):
        super().__init__(transcript_result_stream)
        self.transcript = []
    
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            if not result.is_partial:
                for alt in result.alternatives:
                    self.transcript.append(alt.transcript)

async def stream_transcribe(audio_stream):
    """실시간 음성 인식"""
    client = TranscribeStreamingClient(region=os.getenv('AWS_REGION', 'ap-northeast-2'))
    
    stream = await client.start_stream_transcription(
        language_code="ko-KR",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )
    
    handler = StreamHandler(stream.output_stream)
    
    async def write_chunks():
        async for chunk in audio_stream:
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        await stream.input_stream.end_stream()
    
    await asyncio.gather(write_chunks(), handler.handle_events())
    
    return " ".join(handler.transcript)
