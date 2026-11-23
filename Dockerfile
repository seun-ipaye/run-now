# Production image for Railway: the API and map page, with the prebuilt
# street-network file. No database is needed at runtime.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api/ api/
COPY web/ web/
COPY data/graph/ data/graph/

RUN useradd --create-home app
USER app

# Railway sets PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
