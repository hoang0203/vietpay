# 1. Explicitly pin to bookworm to guarantee OpenJDK 17 availability
FROM python:3.11-slim-bookworm

# 2. Install Java and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /app

# 3. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["./entrypoint.sh"]