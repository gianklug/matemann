FROM python:3.12

RUN pip install --no-cache-dir py-cord==2.6.0 requests==2.32.3

WORKDIR /app
COPY . /app

ENTRYPOINT ["python", "bot.py"]
