FROM node:20-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-venv python3-pip build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY api/package*.json ./api/
RUN cd api && npm install --omit=dev

COPY engine/requirements.txt ./engine/requirements.txt
RUN python3 -m venv ./engine/.venv \
  && ./engine/.venv/bin/python -m pip install --upgrade pip \
  && ./engine/.venv/bin/python -m pip install -r ./engine/requirements.txt

COPY api ./api
COPY engine ./engine

WORKDIR /app/api

ENV NODE_ENV=production
EXPOSE 4000

CMD ["node", "src/server.js"]
