FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src UPTIMEOPS_DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY frontend ./frontend
RUN useradd --create-home --uid 10001 uptime && mkdir -p /app/data && chown -R uptime:uptime /app/data
USER uptime
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "uptimeops.api:app", "--host", "0.0.0.0", "--port", "8002"]
