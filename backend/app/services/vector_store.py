from __future__ import annotations

"""Chroma-backed vector store for playbook and vendor document chunks.

Embedding backend: Gemini text-embedding-004 (768-dim) when GEMINI_API_KEY is
set; falls back to deterministic hash embeddings (192-dim) otherwise.

If you switch embedding backends mid-deployment, clear the Chroma store first:
    Remove-Item -Recurse storage\\chroma
The _ensure_collection() helper also detects dimension mismatches automatically
and recreates the affected collection on startup.
"""

import logging

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.settings import get_settings
from app.services.gemini_embeddings import embed_document_batch, embed_query, embedding_dim

log = logging.getLogger(__name__)
settings = get_settings()
_client = chromadb.PersistentClient(path=str(settings.chroma_path))

_DIM_META_KEY = "_embedding_dim"


def _ensure_collection(name: str) -> Collection:
    """Return collection, recreating it if the stored embedding dimension has changed.

    Dimension is stored in collection metadata under _DIM_META_KEY so that
    mismatches are caught even before any embeddings are inserted (avoids the
    Chroma InvalidArgumentError on the first upsert after a backend switch).
    """
    expected = embedding_dim()
    coll = _client.get_or_create_collection(name)

    # Check dim stored in metadata (reliable even on empty collections)
    stored_dim = coll.metadata.get(_DIM_META_KEY) if coll.metadata else None
    if stored_dim is not None and int(stored_dim) != expected:
        log.warning(
            "[vector_store] Collection '%s' dim mismatch (stored=%s, expected=%s) — recreating.",
            name, stored_dim, expected,
        )
        _client.delete_collection(name)
        coll = _client.create_collection(name, metadata={_DIM_META_KEY: expected})
    elif stored_dim is None:
        # Stamp the dimension into metadata for future checks
        try:
            _client.delete_collection(name)
            coll = _client.create_collection(name, metadata={_DIM_META_KEY: expected})
        except Exception:
            pass

    return coll


class VectorStore:
    def __init__(self) -> None:
        self._playbook_collection = _ensure_collection("playbook_chunks")
        self._vendor_collection = _ensure_collection("vendor_chunks")

    def _collection_for_owner(self, owner_type: str) -> Collection:
        return self._playbook_collection if owner_type == "playbook" else self._vendor_collection

    def upsert_chunks(self, owner_type: str, items: list[dict]) -> None:
        if not items:
            return
        collection = self._collection_for_owner(owner_type)
        texts = [item["text"] for item in items]
        embeddings = embed_document_batch(texts)
        try:
            collection.upsert(
                ids=[item["id"] for item in items],
                documents=texts,
                embeddings=embeddings,
                metadatas=[item["metadata"] for item in items],
            )
        except Exception as exc:
            if "dimension" in str(exc).lower() or "InvalidArgument" in type(exc).__name__:
                # Dim mismatch on existing collection — reset and retry once
                log.warning(
                    "[vector_store] Dimension error on upsert (%s) — recreating collection '%s' and retrying.",
                    exc, owner_type,
                )
                name = "playbook_chunks" if owner_type == "playbook" else "vendor_chunks"
                expected = embedding_dim()
                _client.delete_collection(name)
                collection = _client.create_collection(name, metadata={_DIM_META_KEY: expected})
                if owner_type == "playbook":
                    self._playbook_collection = collection
                else:
                    self._vendor_collection = collection
                collection.upsert(
                    ids=[item["id"] for item in items],
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=[item["metadata"] for item in items],
                )
            else:
                raise

    def query(self, owner_type: str, query_text: str, where: dict, top_k: int = 5) -> list[dict]:
        collection = self._collection_for_owner(owner_type)
        try:
            query_vec = embed_query(query_text)
        except Exception as exc:
            raise RuntimeError(
                f"Embedding query failed — Gemini API may be unavailable. "
                f"Check GEMINI_API_KEY and network connectivity. Error: {exc}"
            ) from exc
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        records: list[dict] = []
        for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
            records.append(
                {
                    "text": document,
                    "metadata": metadata,
                    "score": max(0.0, 1.0 - float(distance)),
                }
            )
        return records


vector_store = VectorStore()
