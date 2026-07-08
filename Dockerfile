# AISHA educational demo - app container (Streamlit UI by default, REST API optional).
#
# This image does NOT bundle Ollama. Run Ollama on the host (or another
# container) and point the app at it with STAI_OLLAMA_BASE_URL. Required models
# must be pulled on the Ollama side:
#   ollama pull llama3.1:8b && ollama pull qwen2.5:3b-instruct && ollama pull nomic-embed-text
#
# Build:  docker build -t aisha-demo .
# Run UI: docker run -p 8501:8501 -e STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434 aisha-demo
# Run API: docker run -p 8000:8000 -e STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434 \
#            aisha-demo uv run uvicorn stai.api:app --host 0.0.0.0 --port 8000
#
# First run only - build the knowledge base inside the container (needs Ollama up):
#   docker exec <container> uv run python -m stai.ingestion

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Slow links kill large wheel downloads at uv's default 30s timeout.
ENV UV_HTTP_TIMEOUT=300

# Dependency layer first so code edits don't bust the package cache.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY app.py ./
COPY data ./data
RUN uv sync --frozen --no-dev

# host.docker.internal reaches the host's Ollama from Docker Desktop
# (Windows/macOS). On Linux, pass --add-host=host.docker.internal:host-gateway
# or override with the Ollama container's address.
ENV STAI_OLLAMA_BASE_URL=http://host.docker.internal:11434

EXPOSE 8501 8000

CMD ["uv", "run", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
