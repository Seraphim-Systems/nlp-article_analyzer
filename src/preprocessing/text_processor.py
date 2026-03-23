"""
NLP Text Preprocessing Module.

Provides standard NLP cleaning:
- Lowercasing
- Punctuation removal
- Tokenization
- Stopword removal
- Lemmatization (using SpaCy)
- Extra whitespace removal
"""

from __future__ import annotations

import logging
import re
import string
from functools import lru_cache
from typing import Any

import spacy
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)


class TextProcessor:
    """
    Standardizes and cleans text for NLP tasks.
    """

    def __init__(self, lang: str = "en"):
        """
        Initialize processor with specific language.

        Parameters
        ----------
        lang : str
            ISO language code (default "en")
        """
        self.lang = lang
        try:
            # Load SpaCy model for lemmatization
            # Fallback to English if model not found for specific language
            model_name = "en_core_web_sm" if lang == "en" else f"{lang}_core_news_sm"
            try:
                self.nlp = spacy.load(model_name, disable=["parser", "ner"])
            except OSError:
                logger.warning("SpaCy model %s not found. Falling back to en_core_web_sm.", model_name)
                self.nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
            
            # Load NLTK stopwords
            try:
                self.stop_words = set(stopwords.words("english" if lang == "en" else lang))
            except LookupError:
                import nltk
                nltk.download("stopwords", quiet=True)
                self.stop_words = set(stopwords.words("english"))

        except Exception as e:
            logger.exception("Failed to initialize TextProcessor: %s", e)
            raise

    def clean_text(
        self, 
        text: str, 
        remove_stopwords: bool = True,
        lemmatize: bool = True,
        lowercase: bool = True
    ) -> str:
        """
        Clean text with standard NLP pipeline.

        Parameters
        ----------
        text : str
            Input text to clean
        remove_stopwords : bool
            Whether to remove common stopwords
        lemmatize : bool
            Whether to reduce words to their base form
        lowercase : bool
            Whether to convert to lowercase

        Returns
        -------
        str
            Cleaned and normalized text
        """
        if not text:
            return ""

        # 1. Basic cleaning: remove extra whitespace and non-printable characters
        text = re.sub(r"\s+", " ", text).strip()
        
        # 2. Lowercase if requested
        if lowercase:
            text = text.lower()

        # 3. SpaCy processing (Lemmatization and Tokenization)
        doc = self.nlp(text)
        
        tokens = []
        for token in doc:
            # Skip punctuation, whitespace, and numbers (optional, keeping numbers for now)
            if token.is_punct or token.is_space:
                continue
                
            # Get lemmatized or raw text
            word = token.lemma_ if lemmatize else token.text
            
            # Skip stopwords if requested
            if remove_stopwords and word in self.stop_words:
                continue
                
            # Skip very short words (usually artifacts)
            if len(word) < 2 and word not in string.digits:
                continue

            tokens.append(word)

        return " ".join(tokens)

    def batch_process(self, texts: list[str], **kwargs: Any) -> list[str]:
        """
        Process multiple texts efficiently using SpaCy's nlp.pipe.
        """
        # SpaCy's nlp.pipe is faster for large batches
        # But we need to apply our custom filtering logic
        
        results = []
        # Re-enabling parser/ner if needed, but keeping disabled for speed
        for doc in self.nlp.pipe(texts, batch_size=50):
            tokens = []
            for token in doc:
                if token.is_punct or token.is_space:
                    continue
                
                word = token.lemma_ if kwargs.get("lemmatize", True) else token.text
                if kwargs.get("lowercase", True):
                    word = word.lower()
                    
                if kwargs.get("remove_stopwords", True) and word in self.stop_words:
                    continue
                    
                if len(word) < 2 and word not in string.digits:
                    continue

                tokens.append(word)
            results.append(" ".join(tokens))
            
        return results


@lru_cache(maxsize=1)
def get_default_processor() -> TextProcessor:
    """Singleton default processor."""
    return TextProcessor()


def preprocess_text(text: str) -> str:
    """Helper function for quick cleaning."""
    return get_default_processor().clean_text(text)
