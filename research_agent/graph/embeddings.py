"""Embedding-based semantic search index for graph nodes.

Uses sentence-transformers for local embedding generation. Falls back
gracefully if the library is unavailable — callers should check
`GraphIndex.available` before relying on semantic search.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded model reference
_model = None
_model_name: str | None = None


def _get_model(model_name: str):
    """Lazy-load the SentenceTransformer model."""
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
        _model_name = model_name
        return _model
    except ImportError:
        logger.warning("sentence-transformers not installed — semantic search unavailable")
        return None
    except Exception as exc:
        logger.warning("Failed to load embedding model %s: %s", model_name, exc)
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


class GraphIndex:
    """In-memory embedding index for graph nodes.

    Lazily initializes the embedding model on first use. Supports
    incremental indexing (index_node) and persistence to disk.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_path: Path | None = None,
    ):
        self.model_name = model_name
        self.index_path = index_path
        self.embeddings: dict[str, np.ndarray] = {}
        self._available: bool | None = None  # lazy check

    @property
    def available(self) -> bool:
        """Check if the embedding model can be loaded."""
        if self._available is None:
            self._available = _get_model(self.model_name) is not None
        return self._available

    def index_node(self, node_id: str, text: str) -> None:
        """Encode and store a single node's text."""
        model = _get_model(self.model_name)
        if model is None:
            return
        self.embeddings[node_id] = model.encode(text, show_progress_bar=False)

    def index_nodes(self, nodes: list[dict[str, Any]]) -> int:
        """Batch-index a list of graph node dicts. Returns count indexed."""
        model = _get_model(self.model_name)
        if model is None:
            return 0

        texts = []
        ids = []
        for node in nodes:
            if node.get("withdrawn"):
                continue
            text = f"{node.get('label', '')} {node.get('description', '')}"
            texts.append(text)
            ids.append(node["id"])

        if not texts:
            return 0

        start = time.monotonic()
        vectors = model.encode(texts, show_progress_bar=False, batch_size=64)
        elapsed = time.monotonic() - start
        logger.info("Indexed %d nodes in %.1fs", len(texts), elapsed)

        for nid, vec in zip(ids, vectors):
            self.embeddings[nid] = vec

        return len(texts)

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the index."""
        self.embeddings.pop(node_id, None)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Semantic search: return (node_id, score) pairs sorted by relevance."""
        model = _get_model(self.model_name)
        if model is None or not self.embeddings:
            return []

        q_vec = model.encode(query, show_progress_bar=False)
        scores = {
            nid: cosine_similarity(q_vec, vec)
            for nid, vec in self.embeddings.items()
        }
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def save(self) -> None:
        """Persist index to disk as .npz file."""
        if not self.index_path or not self.embeddings:
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        ids = list(self.embeddings.keys())
        vectors = np.array([self.embeddings[nid] for nid in ids])
        np.savez(self.index_path, ids=np.array(ids), vectors=vectors)
        logger.info("Saved embedding index to %s (%d nodes)", self.index_path, len(ids))

    def load(self) -> bool:
        """Load index from disk. Returns True if successful."""
        if not self.index_path or not self.index_path.exists():
            return False
        try:
            data = np.load(self.index_path, allow_pickle=False)
            ids = data["ids"]
            vectors = data["vectors"]
            self.embeddings = {str(nid): vec for nid, vec in zip(ids, vectors)}
            logger.info("Loaded embedding index from %s (%d nodes)", self.index_path, len(ids))
            return True
        except Exception as exc:
            logger.warning("Failed to load embedding index: %s", exc)
            return False

    def is_stale(self, graph_path: Path) -> bool:
        """Check if the index is older than the graph file."""
        if not self.index_path or not self.index_path.exists():
            return True
        if not graph_path.exists():
            return False
        return graph_path.stat().st_mtime > self.index_path.stat().st_mtime
