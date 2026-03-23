FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by newspaper3k / lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK and SpaCy resources needed by newspaper3k and preprocessing
ENV NLTK_DATA=/usr/local/share/nltk_data
RUN mkdir -p $NLTK_DATA \
    && python3 -m nltk.downloader -d $NLTK_DATA punkt punkt_tab stopwords averaged_perceptron_tagger_eng \
    && python3 -m spacy download en_core_web_sm

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

