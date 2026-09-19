FROM python:3.12-slim

WORKDIR /app

COPY pesaguard_backend_pipeline/requirements_3.txt ./requirements_3.txt

RUN pip install --no-cache-dir -r requirements_3.txt

COPY . .

RUN mkdir -p /tmp/pesaguard-prometheus \
    && sed -i 's/\r$//' pesaguard_backend_pipeline/worker_entrypoint.sh

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --timeout 120 pesaguard_backend_pipeline.canonical_app:app"]
