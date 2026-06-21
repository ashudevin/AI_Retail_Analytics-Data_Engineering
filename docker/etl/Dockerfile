# Standalone ETL / pipeline runner image (manual runs or pipeline-runner service).
# Build context: project root (..)
FROM python:3.12-slim-bookworm

LABEL maintainer="data-engineering"
LABEL description="AI-Powered Retail Analytics ETL pipeline runner"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        curl \
        procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV RETAIL_ANALYTICS_ROOT=/app
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY sql ./sql
COPY docker/etl/run_pipeline.sh /usr/local/bin/run_pipeline.sh
RUN chmod +x /usr/local/bin/run_pipeline.sh

# Default: idle container (pipeline triggered via Airflow or run_pipeline.sh)
CMD ["tail", "-f", "/dev/null"]
