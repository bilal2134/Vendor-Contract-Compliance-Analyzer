from __future__ import annotations

"""Enterprise-grade embeddings via Google Gemini gemini-embedding-001.

Rate limiting:
  Free tier cap is 100 embed requests/min. We enforce a minimum 0.75s gap
  between API calls (~80 req/min) via a global lock so concurrent threads
  don't blow the quota.

429 handling:
  When the API returns RESOURCE_EXHAUSTED we parse the retryDelay from the
  error body and sleep exactly that long (+ 2s jitter) before retrying.
  We attempt up to _MAX_ATTEMPTS times before raising RuntimeError.

Fallback:
  Hash embeddings (192-dim) are ONLY used when GEMINI_API_KEY is absent.
  We never silently downgrade on API errors — that causes Chroma dim mismatches.
"""

import re
import threading
import time
from functools import lru_cache
from typing import Literal

from app.services.hash_embeddings import embed_text as _hash_embed

TaskType = Literal["retrieval_document", "retrieval_query", "semantic_similarity"]

_TASK_TYPE_MAP: dict[str, str] = {
    "retrieval_document": "RETRIEVAL_DOCUMENT",
    "retrieval_query": "RETRIEVAL_QUERY",
    "semantic_similarity": "SEMANTIC_SIMILARITY",
}

_BATCH_SIZE = 1            # 1 text per call — Gemini counts each text against the quota
_MAX_ATTEMPTS = 6          # total attempts per batch (initial + 5 retries)
_MIN_CALL_INTERVAL = 1.0   # seconds — caps us at 60 req/min (safe below free-tier 100/min)
_DEFAULT_429_WAIT = 60.0   # seconds to wait for 429 when retryDelay not parsed
_JITTER = 3.0              # extra seconds added to parsed retryDelay

# ── Global rate limiter ───────────────────────────────────────────────────────
# _last_call_ts doubles as a backoff barrier: when a 429 is received, ANY thread
# can push it far into the future so ALL waiting threads pause automatically.
_rate_lock = threading.Lock()
_last_call_ts: float = 0.0


def _acquire_rate_slot() -> None:
    """Block until the minimum inter-call interval has elapsed."""
    global _last_call_ts
    with _rate_lock:
        now = time.monotonic()
        wait = (_last_call_ts + _MIN_CALL_INTERVAL) - now
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.monotonic()


def _backoff_all_threads(wait_seconds: float) -> None:
    """On a 429, push the global rate slot forward so every thread backs off.

    This prevents the thundering-herd problem where all threads sleep
    independently and then simultaneously retry, hitting the quota again.
    """
    global _last_call_ts
    with _rate_lock:
        # Only ever extend — never shorten an existing backoff
        earliest_next = time.monotonic() + wait_seconds
        needed_ts = earliest_next - _MIN_CALL_INTERVAL
        if _last_call_ts < needed_ts:
            _last_call_ts = needed_ts


def _extract_retry_delay(exc: Exception) -> float:
    """Parse retryDelay from a Gemini 429 ClientError, or return the default."""
    text = str(exc)
    # JSON body: 'retryDelay': '42s'  or  retryDelay: "42.82s"
    for pattern in (
        r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s",
        r"retry\s+in\s+(\d+(?:\.\d+)?)s",
        r"Please retry in (\d+(?:\.\d+)?)s",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return float(m.group(1)) + _JITTER
    return _DEFAULT_429_WAIT


def _is_rate_limit_error(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "quota" in str(exc).lower()


class GeminiEmbedder:
    """Wraps Gemini Embedding API with rate limiting and 429-aware retries."""

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
        """Embed a list of texts, batching at _BATCH_SIZE items each.

        Falls back to hash embeddings only when Gemini is disabled (no API key).
        On API errors, retries with 429-aware backoff and raises after _MAX_ATTEMPTS.
        """
        if not self.enabled or not texts:
            return [_hash_embed(t) for t in texts]

        results: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            results.extend(self._embed_batch_with_retry(batch, task_type))
        return results

    def _embed_batch_with_retry(
        self, batch: list[str], task_type: TaskType
    ) -> list[list[float]]:
        """Attempt to embed *batch* with rate-limiting and 429-aware retries."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_ATTEMPTS):
            try:
                _acquire_rate_slot()  # respect 80 req/min global rate limit

                if self._backend == "google-genai":
                    response = self._client.models.embed_content(
                        model=self._model,
                        contents=batch,
                        config=self._types.EmbedContentConfig(
                            task_type=_TASK_TYPE_MAP.get(task_type, "RETRIEVAL_DOCUMENT")
                        ),
                    )
                    return [list(e.values) for e in response.embeddings]
                else:
                    # Legacy SDK — embed individually, each acquiring its own rate slot
                    embeddings: list[list[float]] = []
                    for text in batch:
                        _acquire_rate_slot()
                        embeddings.append(
                            list(
                                self._client.embed_content(
                                    model=self._model,
                                    content=text,
                                    task_type=task_type,
                                )["embedding"]
                            )
                        )
                    return embeddings

            except Exception as exc:
                last_exc = exc
                is_last = attempt == _MAX_ATTEMPTS - 1
                if is_last:
                    break

                if _is_rate_limit_error(exc):
                    wait = _extract_retry_delay(exc)
                    import logging
                    logging.getLogger(__name__).warning(
                        "Gemini 429 rate-limit on attempt %d/%d — sleeping %.1fs",
                        attempt + 1, _MAX_ATTEMPTS, wait,
                    )
                    # Coordinate: push the global slot so other threads also
                    # back off for the full retryDelay (no thundering herd).
                    _backoff_all_threads(wait)
                    time.sleep(wait)
                else:
                    # Non-quota error: short exponential backoff
                    time.sleep(min(2.0 ** attempt, 30.0))

        raise RuntimeError(
            f"Gemini embedding failed after {_MAX_ATTEMPTS} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    def embed(self, text: str, task_type: TaskType = "retrieval_document") -> list[float]:
        """Embed a single text."""
        return self.embed_batch([text], task_type=task_type)[0]


@lru_cache(maxsize=1)
def _get_embedder() -> GeminiEmbedder:
    return GeminiEmbedder()


# ── Local (sentence-transformers) embedder ────────────────────────────────────


class LocalEmbedder:
    """CPU-based embedder using sentence-transformers all-MiniLM-L6-v2.

    Completely free, no API key, no rate limits.
    Model (~90 MB) is downloaded once and cached by HuggingFace.
    Produces 384-dim embeddings, which are good quality for semantic search.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    DIM = 384

    def __init__(self) -> None:
        import logging
        log = logging.getLogger(__name__)
        log.info("[embeddings] Loading local model %s (first run downloads ~90 MB)...", self.MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.MODEL_NAME)
        log.info("[embeddings] Local model ready.")

    @property
    def dim(self) -> int:
        return self.DIM

    def embed_batch(self, texts: list[str], task_type: TaskType = "retrieval_document") -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed(self, text: str, task_type: TaskType = "retrieval_document") -> list[float]:
        return self.embed_batch([text], task_type=task_type)[0]


@lru_cache(maxsize=1)
def _get_local_embedder() -> LocalEmbedder:
    return LocalEmbedder()


def _active_embedder() -> GeminiEmbedder | LocalEmbedder:
    from app.core.settings import get_settings
    if get_settings().embedding_backend.lower() == "local":
        return _get_local_embedder()
    return _get_embedder()


# ── Public API ────────────────────────────────────────────────────────────────


def embed_document(text: str) -> list[float]:
    """Embed a document chunk for ingestion (RETRIEVAL_DOCUMENT)."""
    return _active_embedder().embed(text, task_type="retrieval_document")


def embed_document_batch(texts: list[str]) -> list[list[float]]:
    """Batch-embed document chunks — preferred for ingestion to minimise API calls."""
    return _active_embedder().embed_batch(texts, task_type="retrieval_document")


def embed_query(text: str) -> list[float]:
    """Embed a search query (RETRIEVAL_QUERY for asymmetric retrieval)."""
    return _active_embedder().embed(text, task_type="retrieval_query")


def embedding_dim() -> int:
    """Return the active embedding dimensionality."""
    return _active_embedder().dim