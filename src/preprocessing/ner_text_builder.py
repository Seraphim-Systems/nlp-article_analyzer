"""
Build NER-preprocessed text from a raw article body and its extracted entities.

Replaces entity spans with TYPE_word tokens (e.g. LOC_New_York), then applies
the standard preprocessing pipeline (stopword removal, lemmatization) while
preserving those tokens intact.

Called once during the classify job and stored as ner_preprocessed_text.
"""

from __future__ import annotations

import re

_NER_TOKEN_RE = re.compile(r'\b(?:PER|ORG|LOC|MISC)_\S+')


def build_ner_preprocessed_text(body: str, entities: list[dict]) -> str:
    """
    Replace entity spans in body with TYPE_word tokens, then preprocess.

    Parameters
    ----------
    body:     raw article body text
    entities: list of {label, text, start, end} dicts from NER extraction
    """
    if not body:
        return ""

    ner_body = " ".join(body.split())
    ents = sorted(entities, key=lambda e: e.get("start", 0), reverse=True)
    for ent in ents:
        label = ent.get("label", "MISC")
        text  = ent.get("text", "").replace(" ", "_")
        s, e  = ent.get("start", 0), ent.get("end", 0)
        if 0 <= s < e <= len(ner_body):
            ner_body = ner_body[:s] + f"{label}_{text}" + ner_body[e:]

    return _preprocess_preserving_ner(ner_body)


def _preprocess_preserving_ner(text: str) -> str:
    from preprocessing.text_processor import get_default_processor

    saved: list[str] = []

    def _stash(m: re.Match) -> str:  # type: ignore[type-arg]
        saved.append(m.group(0))
        return f"XNERX{len(saved) - 1}X"

    swapped = _NER_TOKEN_RE.sub(_stash, text)
    preprocessed = get_default_processor().clean_text(swapped)
    for i, tok in enumerate(saved):
        preprocessed = preprocessed.replace(f"xnerx{i}x", tok)
    return preprocessed
