FROM python:3.12-slim

WORKDIR /app

COPY backend/ .

RUN pip install --no-cache-dir -e .

CMD ["bash", "start.sh"]
