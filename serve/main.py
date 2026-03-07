import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.client import PFClient
from dotenv import load_dotenv

from autobiographies.generate_autobiography.router import (
    router as autobiographies_generate_autobiography_router,
)
from interviews.interview_chat_v2.router import (
    router as interviews_request_interview_chat_v2_router,
)
from interviews.interview_summary.router import (
    router as interviews_summary_router,
)
from images import router as images_router
from voice.router import router as voice_router

from logs import get_logger
import stream.consumers  # 컨슈머 자동 시작
import logging

load_dotenv()

logger = get_logger()

# promptflow 로그 레벨 조정
logging.getLogger("flowinvoker").setLevel(logging.WARNING)
logging.getLogger("execution.flow").setLevel(logging.WARNING)


def create_connection():
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    connection = None
    if api_key.startswith("sk-"):
        connection = OpenAIConnection(
            name="open_ai_connection",
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        )
    else:
        connection = AzureOpenAIConnection(
            name="open_ai_connection",
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            api_base=os.environ.get("AZURE_OPENAI_API_BASE"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_API_BASE", "azure"),
            api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2023-07-01-preview"
            ),
        )

    pf = PFClient()
    conn = pf.connections.create_or_update(connection)

    logger.info(f"Successfully created connection {conn}")


create_connection()

app = FastAPI(
    description="Life Bookshelf AI API",
    version="0.0.1",
)

web_url = os.environ.get("WEB_URL")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", web_url],  # 개발용, 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

web_url = os.environ.get("WEB_URL")
# 유지되는 API들

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", web_url],  # 개발용, 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 유지되는 API들
app.include_router(autobiographies_generate_autobiography_router, prefix="/api/v2/autobiographies")
app.include_router(interviews_request_interview_chat_v2_router, prefix="/api/v2/interviews")
app.include_router(interviews_summary_router, prefix="/api/v2/interviews")
app.include_router(images_router, prefix="/api/v2/images")
app.include_router(voice_router, prefix="/api/v2/voice")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)