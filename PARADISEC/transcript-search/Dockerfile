FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    STORE_DIR=/store \
    ANONYMIZED_TELEMETRY=False

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# The corpus (/data) and the vector store (/store) are mounted at run time; the
# image holds code only. See deploy/paradisec-transcripts/docker-compose.yml.
VOLUME ["/data", "/store"]
EXPOSE 8501

# baseUrlPath is what lets the shared Caddy serve the app under
# /paradisec-transcripts rather than the root of the domain.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.baseUrlPath=paradisec-transcripts"]
