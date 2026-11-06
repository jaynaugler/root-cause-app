FROM python:3.12-slim

# Render's native Python runtime can't install system packages, so the OCR
# fallback in app/pdf.py needs this Docker runtime instead.
RUN apt-get update \
	&& apt-get install -y --no-install-recommends tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

# Render sets $PORT on Docker services (default 10000)
CMD ["sh", "-c", "uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
