FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by newspaper3k / lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK punkt tokenizer (needed by newspaper3k)
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True)"

COPY . .

ENV PYTHONPATH=/app/src:/app
ENV PYTHONUNBUFFERED=1

# Entrypoint handles initialization and service startup
ENTRYPOINT ["python", "scripts/entrypoint.py"]
# Default service (overridable via docker-compose CMD)
CMD ["api"]

