FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY permission_gateway /app/permission_gateway

RUN python -m pip install --no-cache-dir -e .

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "permission_gateway.gateway.app:build_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]

