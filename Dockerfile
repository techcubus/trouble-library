FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN curl -sSL https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js -o /tmp/htmx.min.js

COPY app/ app/
RUN mv /tmp/htmx.min.js app/static/htmx.min.js

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV DATA_DIR=/data \
    MEDIA_INBOX_DIR=/media/inbox \
    MEDIA_LIBRARY_ROOT=/media/library \
    ADMIN_PORT=8001 \
    PUBLIC_PORT=8000

EXPOSE 8000 8001

ENTRYPOINT ["./entrypoint.sh"]
