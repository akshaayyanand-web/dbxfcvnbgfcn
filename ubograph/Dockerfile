# Portable image for hosts that take a Dockerfile (Hugging Face Spaces, Fly.io,
# Koyeb, Cloud Run). Render does not need this — it uses render.yaml.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face Spaces expects 7860; everything else injects $PORT.
ENV PORT=7860
EXPOSE 7860

CMD gunicorn server:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT}
