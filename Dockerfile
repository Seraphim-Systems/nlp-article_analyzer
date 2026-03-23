# syntax=docker/dockerfile:1
# BuildKit required — enables --mount=type=cache for persistent pip cache.
# The pip cache survives `docker compose build --no-cache`, so heavy packages
# (torch, transformers, spacy) are only downloaded once per machine.

FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 1: Heavy ML libs (torch, transformers, spacy, sklearn, numpy, pandas)
# Cached in BuildKit cache — only re-downloaded when requirements-heavy.txt changes.
COPY requirements-heavy.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-heavy.txt

# ── Layer 2: App-level deps (fast to install, changes more often)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# ── Layer 3: NLP model data
ENV NLTK_DATA=/usr/local/share/nltk_data
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p $NLTK_DATA \
    && python3 -m nltk.downloader -d $NLTK_DATA \
        punkt punkt_tab stopwords averaged_perceptron_tagger_eng \
    && python3 -m spacy download en_core_web_sm

# ── Layer 4: Pre-download dslim/bert-base-NER into the image
# Baked in so containers start instantly without downloading at runtime.
RUN python -c "\
from transformers import pipeline; \
pipeline('ner', model='dslim/bert-base-NER', aggregation_strategy='simple'); \
print('NER model pre-downloaded.')"

# ── Layer 5: Application source (changes most often — stays last)
COPY . .

ENV PYTHONPATH=/app/src:/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "scripts/entrypoint.py"]
CMD ["api"]
