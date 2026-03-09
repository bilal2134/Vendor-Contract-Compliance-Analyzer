from __future__ import annotations

"""Chroma-backed vector store for playbook and vendor document chunks.

Embedding backend: Gemini text-embedding-004 (768-dim) when GEMINI_API_KEY is
set; falls back to deterministic hash embeddings (192-dim) otherwise.

If you switch embedding backends mid-deployment, clear the Chroma store first:
    Remove-Item -Recurse storage\\chroma
The _ensure_collection() helper also detects dimension mismatches automatically
and recreates the affected collection on startup.
"""

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.settings import get_settings
from app.services.gemini_embeddings import embed_document_batch, embed_query, embedding_dim

settings = get_settings()
_client = chromadb.PersistentClient(path=str(settings.chroma_path))


def _ensure_collection(name: str) -> Collection:
    """Return collection, recreating it if the stored embedding dimension has changed."""
    coll = _client.get_or_create_collection(name)
    expected = embedding_dim()
    try:
        peeked = coll.peek(limit=1)
        existing_embeddings = peeked.get("embeddings") or []
        if existing_embeddings and len(existing_embeddings[0]) != expected:
            _client.delete_collection(name)
            coll = _client.create_collection(name)
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
        embeddings = embed_document_batch(texts)  # single batched API call
        collection.upsert(
            ids=[item["id"] for item in items],
            documents=texts,
            embeddings=embeddings,
            metadatas=[item["metadata"] for item in items],
        )

    def query(self, owner_type: str, query_text: str, where: dict, top_k: int = 5) -> list[dict]:
        collection = self._collection_for_owner(owner_type)
        result = collection.query(
            query_embeddings=[embed_query(query_text)],  # asymmetric retrieval task type
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
