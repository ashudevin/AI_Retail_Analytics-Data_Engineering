# Custom Airflow image with Java + PySpark pipeline dependencies pre-installed.
# Build context: project root (..)
FROM apache/airflow:2.10.4-python3.12

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        curl \
        procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

USER airflow

# Pre-install pipeline + Airflow extras (avoids slow pip install on every container start)
COPY requirements.txt /tmp/project-requirements.txt
COPY airflow/requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir \
    -r /tmp/airflow-requirements.txt \
    -r /tmp/project-requirements.txt

# Bake application source into the image for reproducible builds
COPY --chown=airflow:root src /opt/airflow/project/src
COPY --chown=airflow:root sql /opt/airflow/project/sql

ENV RETAIL_ANALYTICS_ROOT=/opt/airflow/project
ENV PYTHONPATH=/opt/airflow:/opt/airflow/project
