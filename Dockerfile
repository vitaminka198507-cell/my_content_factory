FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CONTENT_FACTORY_HOST=0.0.0.0
ENV CONTENT_FACTORY_PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p output/web tmp

EXPOSE 8000

CMD ["python", "web_app.py"]
