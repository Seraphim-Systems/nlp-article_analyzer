import torch
from transformers import pipeline

_MODEL = "facebook/bart-large-mnli"
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        device = 0 if torch.cuda.is_available() else -1
        _pipeline = pipeline("zero-shot-classification", model=_MODEL, device=device)
    return _pipeline


def classify_topics(text: str, candidate_labels: list[str]):
    nlp = _get_pipeline()
    # BART handles context much better than simple keywords
    result = nlp(text[:1024], candidate_labels, multi_label=False)
    return result["labels"][0], result["scores"][0]
