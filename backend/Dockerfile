FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend source
COPY . /app

# Install CPU-only torch first, then the rest
RUN set -eux \
    && if [ -f /app/requirements.txt ]; then \
         pip install --no-cache-dir \
           torch --index-url https://download.pytorch.org/whl/cpu \
           && pip install --no-cache-dir -r /app/requirements.txt; \
       fi

ENV BACKEND_PORT=8013
EXPOSE 8013

# Default command
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${BACKEND_PORT}"]
