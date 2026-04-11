import hashlib
import math
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import logging

from langchain_community.embeddings import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)


_EMBEDDING_MODEL = None


class FallbackHashingEmbeddings:
    """Deterministic local fallback when sentence-transformers cannot load."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def _tokenize(self, text: str):
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    def _embed(self, text: str):
        vector = [0.0] * self.dimensions
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % self.dimensions
            weight = (int(digest[8:12], 16) % 1000) / 1000.0 + 0.1
            vector[bucket] += weight

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text):
        return self._embed(text)


def _load_hf_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_embedding_model(timeout_seconds: int = 10):
    """Load a local HuggingFace embedding model with a safe fallback."""

    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_load_hf_embeddings)
            _EMBEDDING_MODEL = future.result(timeout=timeout_seconds)
            return _EMBEDDING_MODEL
    except (TimeoutError, Exception):
        _EMBEDDING_MODEL = FallbackHashingEmbeddings()
        return _EMBEDDING_MODEL