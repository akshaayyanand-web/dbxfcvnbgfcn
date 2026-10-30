# FLAME IN FREEFALL - API image
# BASE_IMAGE can point at a registry mirror (e.g. mirror.gcr.io/library/python:3.13-slim) if Docker Hub is rate-limited.
ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Optional extra CA certificates (e.g. a corporate TLS proxy): put *.crt files in docker/extra-ca/.
COPY docker/extra-ca/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# ffmpeg/ffprobe: reliable decoding of interlaced H.264 and VFR timestamps (SCIENTIFIC_ASSUMPTIONS A-CV-10).
# Package sources are switched to HTTPS.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY data/presets/ data/presets/
COPY data/processed/ data/processed/
COPY models/ models/

RUN useradd --create-home --uid 10001 flame && mkdir -p /app/storage /app/data/raw && chown -R flame /app/storage
USER flame

ENV FLAME_STORAGE_DIR=/app/storage FLAME_DATA_DIR=/app/data FLAME_MODELS_DIR=/app/models
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else 1)"
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
