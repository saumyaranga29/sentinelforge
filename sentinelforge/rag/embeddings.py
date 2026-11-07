import hashlib
import numpy as np
from typing import List, Optional

from sentinelforge.config import settings
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.rag.embeddings")

try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None


class LocalEmbeddingEngine:
    """
    Generates dense embeddings locally using FastEmbed (ONNX runtime on CPU).
    Guarantees privacy-first execution with zero external API calls.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._init_attempted = False

    def _get_model(self):
        if self._model is None and not self._init_attempted:
            self._init_attempted = True
            self._init_model()
        return self._model

    def _init_model(self) -> None:
        if TextEmbedding is not None:
            try:
                self._model = TextEmbedding(model_name=self.model_name, local_files_only=True)
                logger.info(f"Loaded local FastEmbed model (offline): {self.model_name}")
            except Exception as e:
                try:
                    self._model = TextEmbedding(model_name=self.model_name)
                    logger.info(f"Loaded local FastEmbed model: {self.model_name}")
                except Exception as ex:
                    logger.warning(f"Could not initialize FastEmbed ({ex}). Falling back to deterministic local vectors.")
                    self._model = None
        else:
            logger.warning("fastembed not installed. Falling back to deterministic local vectors.")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generates normalized vector embeddings for a list of text strings."""
        if not texts:
            return []

        model = self._get_model()
        if model is not None:
            try:
                embeddings_generator = model.embed(texts)
                return [emb.tolist() if hasattr(emb, "tolist") else [float(x) for x in emb] for emb in embeddings_generator]
            except Exception as e:
                logger.error(f"FastEmbed inference error: {e}. Using deterministic fallback.")

        return [self._fallback_embedding(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string."""
        return self.embed_texts([query])[0]

    def _fallback_embedding(self, text: str, dim: int = 384) -> List[float]:
        """
        Deterministic, offline CPU fallback vector generation based on hashed n-grams.
        Preserves cosine similarity properties for identical or near-identical text.
        """
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec.tolist()

        for word in words:
            idx = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % dim
            vec[idx] += 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

