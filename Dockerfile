FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin aisha

WORKDIR /app
ENV UV_HTTP_TIMEOUT=300 \
    UV_LINK_MODE=copy \
    STAI_DB_PATH=/app/data/stai.db \
    STAI_CHROMA_DIR=/app/data/chroma \
    STAI_OBS_LOG_PATH=/app/data/observability.jsonl \
    STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY app.py ./
COPY handbook ./handbook
COPY deploy ./deploy
RUN mkdir -p /app/data \
    && uv sync --frozen --no-dev \
    && chown -R aisha:aisha /app

USER aisha
VOLUME ["/app/data"]
EXPOSE 8501 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["uv", "run", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
