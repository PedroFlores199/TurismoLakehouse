FROM python:3.12-slim-trixie AS web
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd -m app
COPY tourism ./tourism
COPY data ./data
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "tourism.web:app", "--host", "0.0.0.0", "--port", "8000"]

FROM web AS etl
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless && rm -rf /var/lib/apt/lists/*
COPY requirements-etl.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-etl.lock && mkdir /lake && chown app:app /lake
USER app
ENTRYPOINT ["python", "-m", "tourism.pipeline", "--root", "/lake"]
CMD []
