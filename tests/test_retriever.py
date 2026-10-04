"""Tests for Hybrid Retriever (Dense + Sparse BM25 + RRF)."""
from src.retriever import HybridRetriever


def test_hybrid_retriever_initialization():
    retriever = HybridRetriever()
    assert len(retriever.chunks) > 0
    assert len(retriever.doc_freqs) > 0
    assert retriever.total_docs > 0
    assert retriever.avg_doc_len > 0

def test_hybrid_retriever_query():
    retriever = HybridRetriever()
    results = retriever.retrieve("UIET placements highest package", top_k=3)
    assert len(results) > 0
    top = results[0]
    assert "text" in top
    assert "metadata" in top
    assert "rrf_score" in top
    assert top["rrf_score"] > 0
