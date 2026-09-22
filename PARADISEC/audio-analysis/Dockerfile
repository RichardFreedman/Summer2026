FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba

# curl and tar fetch the audio excerpts; libsndfile ships inside the soundfile wheel.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# The 190 excerpts and their metadata come from github.com/dan321/soundscape,
# pinned to a commit so builds are reproducible. Done before copying the code
# so that code changes do not re-download 60 MB of audio.
ARG SOUNDSCAPE_COMMIT=60b60a3324c9ee08e76076ebbbc427878435592e
COPY fetch_data.sh .
RUN ./fetch_data.sh "$SOUNDSCAPE_COMMIT"

COPY . .

EXPOSE 8501

# baseUrlPath is what lets the shared Caddy serve the app under
# /paradisec-audio-analysis rather than the root of the domain.
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.baseUrlPath=paradisec-audio-analysis"]
