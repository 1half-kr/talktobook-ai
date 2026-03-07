FROM python:3.10-slim

RUN mkdir -p /app/serve/
WORKDIR /app/serve/

# Promptflow 구버전 흔적 제거
RUN pip uninstall -y promptflow promptflow-core promptflow-devkit promptflow-azure || true

COPY ai/requirements.txt requirements.txt

# Promptflow 1.7.x는 marshmallow 3.19.0 필요
RUN pip install --no-cache-dir --upgrade --no-deps marshmallow==3.19.0

# keyring 대안 설치 (Docker 환경용)
RUN pip install --no-cache-dir keyrings.alt

# 모든 의존성 설치
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ai/serve/ /app/serve/
COPY ai/flows/ /app/flows/
COPY deploy/ai/promtail-config.yml /etc/promtail-config.yml

# FastAPI 실행 - PYTHONPATH 명시적 설정
CMD ["sh", "-c", "cd /app/serve && PYTHONPATH=/app/serve:$PYTHONPATH uvicorn main:app --host 0.0.0.0 --port 3000"]
