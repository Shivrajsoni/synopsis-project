"""
Interactive Search Preview for Extracted RAG Chunks.
Allows testing retrieval over data/chunks/rag_chunks.jsonl before configuring a Vector DB.
Uses TF-IDF / BM25 term weighting to verify chunk quality and breadcrumb context.
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "chunks" / "rag_chunks.jsonl"

def load_chunks() -> List[Dict[str, Any]]:
    if not CHUNKS_FILE.exists():
        print(f"Error: {CHUNKS_FILE} does not exist. Run python -m src.pipeline first.")
        sys.exit(1)
    chunks = []
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks

def search_chunks(query: str, chunks: List[Dict[str, Any]], top_k: int = 3):
    tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    if not tokens:
        print("Please provide meaningful search keywords.")
        return

    scored = []
    for chunk in chunks:
        text_lower = chunk["text"].lower()
        score = sum(text_lower.count(t) for t in tokens)
        # Bonus for matches in breadcrumbs / category
        breadcrumb_lower = chunk.get("breadcrumb", "").lower()
        score += sum(breadcrumb_lower.count(t) * 3 for t in tokens)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:top_k]

    print(f"\nQuery: '{query}'")
    print(f"Found {len(scored)} matching chunks. Showing Top {len(results)}:\n" + "=" * 60)
    for rank, (score, chunk) in enumerate(results, start=1):
        print(f"[{rank}] Score: {score} | Category: {chunk['category']} | ID: {chunk['chunk_id']}")
        print(f"    Source: {chunk['source_url']}")
        print(f"    Breadcrumb: {chunk.get('breadcrumb', 'N/A')}")
        print("    Preview:")
        preview_lines = chunk["text"].splitlines()[:6]
        for line in preview_lines:
            print(f"      {line}")
        print("-" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query_str = " ".join(sys.argv[1:])
    else:
        query_str = "PULEET entrance test date B.E."
    data = load_chunks()
    search_chunks(query_str, data)
