FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --system app
COPY alembic.ini ./
COPY alembic ./alembic
USER app
EXPOSE 8000
CMD ["uvicorn", "bagmitra_api.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
