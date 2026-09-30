FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Utilisateur non root ; le volume /data (audio, covers) lui appartient
RUN useradd --uid 1000 --create-home musicapp \
    && mkdir -p /data/audio /data/covers \
    && chown -R musicapp:musicapp /data
USER musicapp

EXPOSE 8000

# Une instance = gunicorn + workers uvicorn (WEB_CONCURRENCY = nombre de cœurs)
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000 --access-logfile -"]
