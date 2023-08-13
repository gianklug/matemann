FROM python:3.11

RUN pip install --no-cache-dir py-cord==2.4.1 requests==2.31.0

WORKDIR /app
COPY . /app

ENTRYPOINT ["python", "bot.py"]
