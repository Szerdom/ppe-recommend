FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app.py ./
COPY ppe ./ppe

EXPOSE 8501 5000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)" || exit 1
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]
