FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by newspaper3k / lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK punkt tokenizer (needed by newspaper3k)
RUN python -c "import nltk; nltk.download('punkt_tab', quiet=True); nltk.download('stopwords', quiet=True)"

# Pre-download dslim/bert-base-NER to bake it into the image layer
RUN python -c "\
from transformers import pipeline; \
pipeline('ner', model='dslim/bert-base-NER', aggregation_strategy='simple'); \
print('NER model pre-downloaded.')"

COPY . .

ENV PYTHONPATH=/app/src:/app
ENV PYTHONUNBUFFERED=1

# Entrypoint handles initialization and service startup
ENTRYPOINT ["python", "scripts/entrypoint.py"]
# Default service (overridable via docker-compose CMD)
CMD ["api"]

