FROM node:25-alpine AS base

WORKDIR /app

COPY ./server/frontend/ ./

RUN npm install && npm run build

FROM python:3.13-alpine as prod
COPY ./server/backend/ ./backend/

RUN apt-get update &&  apt-get -y install git && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade -r ./server/requirments.txt

COPY --from=base /app/build ./backend/static

CMD ["/bin/sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 80 --proxy-headers --forwarded-allow-ips=\"*\" --workers 1"]
