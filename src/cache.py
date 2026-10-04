"""
Semantic Caching Layer for University RAG.
Stores question embeddings and verified responses with citations.
Uses Cosine Similarity on normalized all-MiniLM-L6-v2 ONNX embeddings.
If a new query has Cosine Similarity >= similarity_threshold (default 0.93)
with an existing cached query, the cached response is returned in < 5ms.
"""
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from chromadb.utils import embedding_functions

logger = logging.getLogger("SemanticCache")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "semantic_cache.json"

class SemanticCache:
    """
    In-memory semantic cache with disk persistence and cosine similarity thresholding.
    """
    def __init__(self, cache_file: Path = CACHE_FILE, default_threshold: float = 0.93):
        self.cache_file = cache_file
        self.default_threshold = default_threshold
        self.lock = threading.Lock()
        self.ef = embedding_functions.DefaultEmbeddingFunction()

        self.queries: List[str] = []
        self.vectors: List[np.ndarray] = []  # Normalized 384-d vectors
        self.payloads: List[Dict[str, Any]] = []

        self.hits = 0
        self.misses = 0

        self._load_cache()

    def _load_cache(self):
        """Loads persistent cache from disk if available."""
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                q = item["query"]
                vec = np.array(item["vector"], dtype=np.float32)
                # Ensure normalized
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                self.queries.append(q)
                self.vectors.append(vec)
                self.payloads.append(item["payload"])
            logger.info(f"Loaded {len(self.queries)} semantic cache entries from {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to load semantic cache: {e}")

    def _save_cache(self):
        """Saves cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            export_data = []
            for q, vec, payload in zip(self.queries, self.vectors, self.payloads):
                export_data.append({
                    "query": q,
                    "vector": vec.tolist(),
                    "payload": payload
                })
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist semantic cache: {e}")

    def get(self, query: str, threshold: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Computes cosine similarity between new query embedding and all cached embeddings.
        Returns payload if similarity >= threshold, else None.
        """
        th = threshold if threshold is not None else self.default_threshold
        query_clean = query.strip()
        if not query_clean or not self.vectors:
            self.misses += 1
            return None

        # Embed incoming query
        try:
            raw_vec = np.array(self.ef([query_clean])[0], dtype=np.float32)
            norm = np.linalg.norm(raw_vec)
            if norm == 0:
                self.misses += 1
                return None
            q_vec = raw_vec / norm
        except Exception as e:
            logger.error(f"Error embedding query for cache: {e}")
            self.misses += 1
            return None

        with self.lock:
            if not self.vectors:
                self.misses += 1
                return None

            # Vectorized dot product against all cached vectors
            matrix = np.vstack(self.vectors)  # Shape (N, 384)
            sims = np.dot(matrix, q_vec)      # Shape (N,)

            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])

            if best_sim >= th:
                self.hits += 1
                cached_payload = self.payloads[best_idx].copy()
                cached_payload["cached"] = True
                cached_payload["cached_query"] = self.queries[best_idx]
                cached_payload["similarity"] = round(best_sim, 4)
                logger.info(f"⚡ Semantic Cache HIT! (Sim: {best_sim:.4f} >= {th}) for '{query_clean}' -> '{self.queries[best_idx]}'")
                return cached_payload

            self.misses += 1
            return None

    def set(self, query: str, answer: str, citations: List[Dict[str, Any]], model: str = "llama3.2:3b"):
        """
        Caches a verified query-response pair.
        """
        query_clean = query.strip()
        if not query_clean or not answer:
            return

        try:
            raw_vec = np.array(self.ef([query_clean])[0], dtype=np.float32)
            norm = np.linalg.norm(raw_vec)
            if norm == 0:
                return
            q_vec = raw_vec / norm
        except Exception as e:
            logger.error(f"Error embedding query to set in cache: {e}")
            return

        with self.lock:
            # Check if identical query already exists
            if query_clean in self.queries:
                idx = self.queries.index(query_clean)
                self.vectors[idx] = q_vec
                self.payloads[idx] = {
                    "answer": answer,
                    "citations": citations,
                    "model": model
                }
            else:
                self.queries.append(query_clean)
                self.vectors.append(q_vec)
                self.payloads.append({
                    "answer": answer,
                    "citations": citations,
                    "model": model
                })

            self._save_cache()
            logger.info(f"Cached query: '{query_clean}' (Total entries: {len(self.queries)})")

    def stats(self) -> Dict[str, Any]:
        """Returns cache telemetry."""
        total_lookups = self.hits + self.misses
        hit_rate = (self.hits / total_lookups * 100) if total_lookups > 0 else 0.0
        return {
            "total_entries": len(self.queries),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2)
        }
