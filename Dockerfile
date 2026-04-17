# ModelForge on-prem container image (US-025)
#
# Multi-stage build:
#   1. `builder` — install Python deps into a venv
#   2. `runtime` — slim final image, non-root user, HEALTHCHECK on /health

FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for pdfplumber / openpyxl / reportlab
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ModelForge with web + ingest extras. Source COPY last so
# changes to source don't invalidate the pip layer.
COPY pyproject.toml README.md ./
COPY modelforge ./modelforge
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[web,ingest]"


FROM python:3.12-slim AS runtime

# Non-root user
RUN groupadd --system modelforge \
    && useradd --system --gid modelforge --home /home/modelforge modelforge

# Copy Python env from the builder
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/modelforge /usr/local/bin/modelforge
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Session-data mount point
RUN mkdir -p /data && chown modelforge:modelforge /data

USER modelforge
WORKDIR /home/modelforge

ENV MODELFORGE_SESSION_DIR=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Liveness — `/health` returns 200 with {status:"ok"}
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); \
sys.exit(0 if r.status==200 else 1)"

# Default: launch the web thin layer bound to 0.0.0.0:8000.
# Override CMD for CLI-only use:
#   docker run --rm modelforge:latest modelforge build /data/spec.yaml
CMD ["modelforge", "serve", "--host", "0.0.0.0", "--port", "8000", \
     "--session-dir", "/data"]
