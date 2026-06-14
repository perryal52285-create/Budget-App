ARG BUILD_FROM

# ---- stage 1: build the React frontend -----------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: python runtime ---------------------------------------------
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 PYTHONUNBUFFERED=1

WORKDIR /opt/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh

COPY app ./app
# Built SPA from stage 1 -> served by FastAPI at /ui
COPY --from=frontend /build/dist ./app/frontend_dist

CMD [ "/run.sh" ]
