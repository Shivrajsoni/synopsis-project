"""Tests for Semantic Cache Layer."""
import tempfile
from pathlib import Path

from src.cache import SemanticCache


def test_semantic_cache_hit_and_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = SemanticCache(cache_file=cache_path, default_threshold=0.90)

        # Initially empty
        assert cache.get("What is UIET placement?") is None

        # Store entry
        citations = [{"source_url": "https://uiet.puchd.ac.in", "breadcrumb": "Placements"}]
        cache.set(
            query="What is the highest package in UIET placements?",
            answer="The highest package is 45 LPA.",
            citations=citations,
            model="llama3.2:3b"
        )

        # Exact match
        hit = cache.get("What is the highest package in UIET placements?")
        assert hit is not None
        assert "45 LPA" in hit["answer"]

        # Near match (Cosine similarity)
        near_hit = cache.get("highest package in UIET placement?")
        assert near_hit is not None
        assert "45 LPA" in near_hit["answer"]

        # Different query should miss
        miss = cache.get("How many hostel rooms are in Panjab University?")
        assert miss is None
