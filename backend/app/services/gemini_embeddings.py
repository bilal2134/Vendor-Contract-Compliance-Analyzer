from __future__ import annotations

"""Enterprise-grade embeddings via Google Gemini text-embedding-004.

Falls back to deterministic hash embeddings when:
  - GEMINI_API_KEY is not configured
  - Any Gemini API call fails (network error, quota, model error)

Embedding dimensions:
  Gemini text-embedding-004 → 768-dim  (enterprise-grade semantic retrieval)
  Hash fallback              → 192-dim  (deterministic, zero external dependency)

IMPORTANT: After switching embedding backends clear the Chroma store so
           dimension mismatches don't cause query failures:
               Remove-Item -Recurse storage\\chroma
           VectorStore._ensure_collection() also handles this automatically
           by detecting dimension mismatches and recreating the collection.
"""

from functools import lru_cache
from typing import Literal

from app.services.hash_embeddings import embed_text as _hash_embed

TaskType = Literal["retrieval_document", "retrieval_query", "semantic_similarity"]

_TASK_TYPE_MAP: dict[str, str] = {
    "retrieval_document": "RETRIEVAL_DOCUMENT",
    "retrieval_query": "RETRIEVAL_QUERY",
    "semantic_similarity": "SEMANTIC_SIMILARITY",
}

_BATCH_SIZE = 100  # Gemini text-embedding-004 max items per embed_content call


class GeminiEmbedder:
    """Wraps Gemini Embedding API with automatic fallback to hash embeddings."""

    GEMINI_DIM = 3072
    HASH_DIM = 192

    def __init__(self) -> None:
        from app.core.settings import get_settings

        settings = get_settings()
        self._model = settings.gemini_embedding_model
        self._backend: str | None = None
        self._client = None
        self._types = None
        self.enabled = False

        if not settings.gemini_api_key:
            return

        # Prefer new google-genai SDK (supports batch + task_type)
        try:
            from google import genai
            from google.genai import types as genai_types

            self._client = genai.Client(api_key=settings.gemini_api_key)
            self._types = genai_types
            self._backend = "google-genai"
            self.enabled = True
            return
        except Exception:
            self._client = None

        # Fall back to legacy google-generativeai SDK
        try:
            import google.generativeai as legacy_genai

            legacy_genai.configure(api_key=settings.gemini_api_key)
            self._client = legacy_genai
            self._backend = "google-generativeai"
            self.enabled = True
        except Exception:
            pass

    @property
    def dim(self) -> int:
        return self.GEMINI_DIM if self.enabled else self.HASH_DIM

    def embed_batch(
        self, texts: list[str], task_type: TaskType = "retrieval_document"
    ) -> list[list[float]]:
        """Embed a list of texts, batching API calls at _BATCH_SIZE items each."""
        if not self.enabled or not texts:
            return [_hash_embed(t) for t in texts]

        results: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            try:
                if self._backend == "google-genai":
                    response = self._client.models.embed_content(
                        model=self._model,
                        contents=batch,
                        config=self._types.EmbedContentConfig(
                            task_type=_TASK_TYPE_MAP.get(task_type, "RETRIEVAL_DOCUMENT")
                        ),
                    )
                    results.extend([list(e.values) for e in response.embeddings])
                else:
                    # Legacy SDK does not support true batch — embed individually
                    for text in batch:
                        r = self._client.embed_content(
                            model=self._model,
                            content=text,
                            task_type=task_type,
                        )
                        results.append(list(r["embedding"]))
            except Exception:
                # Graceful degradation: hash-embed the failed batch
                results.extend([_hash_embed(t) for t in batch])

        return results

    def embed(self, text: str, task_type: TaskType = "retrieval_document") -> list[float]:
        """Embed a single text."""
        return self.embed_batch([text], task_type=task_type)[0]


@lru_cache(maxsize=1)
def _get_embedder() -> GeminiEmbedder:
    return GeminiEmbedder()


# ── Public API ────────────────────────────────────────────────────────────────


def embed_document(text: str) -> list[float]:
    """Embed a document chunk for vector-store ingestion (RETRIEVAL_DOCUMENT)."""
    return _get_embedder().embed(text, task_type="retrieval_document")


def embed_document_batch(texts: list[str]) -> list[list[float]]:
    """Batch-embed document chunks — preferred for ingestion to minimise API calls."""
    return _get_embedder().embed_batch(texts, task_type="retrieval_document")


def embed_query(text: str) -> list[float]:
    """Embed a search query against the index (RETRIEVAL_QUERY for asymmetric retrieval)."""
    return _get_embedder().embed(text, task_type="retrieval_query")


def embedding_dim() -> int:
    """Return the active embedding dimensionality (768 with Gemini, 192 with hash fallback)."""
    return _get_embedder().dim
