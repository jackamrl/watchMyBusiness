FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt requirements-nlp.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu -r requirements-nlp.txt

COPY watchmybusiness ./watchmybusiness

RUN useradd --uid 10001 --no-create-home appli
USER appli

ENTRYPOINT ["python", "-m", "watchmybusiness"]
