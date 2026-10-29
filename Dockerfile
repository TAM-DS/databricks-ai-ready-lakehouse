FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    QUALITY_DATA_DIR=/app/data \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    HOME=/tmp \
    HF_HOME=/tmp/hf_cache
WORKDIR /app
COPY pyproject.toml ./
COPY quality_portal/ ./quality_portal/
RUN pip install --no-cache-dir . \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001:10001
EXPOSE 7860
CMD ["python", "-m", "quality_portal.dashboard"]
