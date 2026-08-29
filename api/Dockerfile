FROM python:3.12-slim
WORKDIR /srv
# ffmpeg: recompressió dels vídeos de fons pujats a l'admin (ver
# services/video.py) — es fa sempre en pujar, mai es guarda l'original.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# UVICORN_WORKERS per defecte a 2: aprofita els 2 vCPU de l'EC2 actual
# (t2.medium). Un sol procés (com era abans) deixa un vCPU sencer sense fer
# res i limita la concurrència real al thread pool intern d'un únic procés
# Python — coll d'ampolla vist en un test de càrrega abans que la CPU o la
# base de dades arribessin al límit. Si es puja la mida de la instància,
# pujar aquesta variable en proporció als vCPU nous (veure docker-compose.prod.yml).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
