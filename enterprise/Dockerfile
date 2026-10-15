FROM python:3.12-slim
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANGSMITH_TRACING=false
WORKDIR /app
COPY enterprise/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.lock && useradd -m -u 10001 rainguard && mkdir /app/runtime && chown rainguard /app/runtime
COPY enterprise /app/enterprise
USER rainguard
EXPOSE 8100
CMD ["python","-m","uvicorn","enterprise.api:create_app","--factory","--host","0.0.0.0","--port","8100","--no-proxy-headers"]
