"""
Vector Store Indexer for University RAG.
Uses ChromaDB with Persistent Client and default all-MiniLM-L6-v2 ONNX embeddings.
Indexes chunks from data/chunks/rag_chunks.jsonl and enables metadata-filtered search.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import chromadb

logger = logging.getLogger("VectorStore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_FILE = PROJECT_ROOT / "data" / "chunks" / "rag_chunks.jsonl"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"
COLLECTION_NAME = "panjab_university_rag"

def get_chroma_client() -> chromadb.PersistentClient:
    """Returns persistent ChromaDB client."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))

def build_vector_index(force_rebuild: bool = False):
    """
    Reads data/chunks/rag_chunks.jsonl and indexes into ChromaDB collection.
    """
    if not CHUNKS_FILE.exists():
        logger.error(f"Chunks file missing at {CHUNKS_FILE}. Run pipeline first.")
        return

    client = get_chroma_client()

    if force_rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info(f"Deleted existing collection '{COLLECTION_NAME}' for rebuild.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Panjab University & UIET RAG Knowledge Base"}
    )

    # Check if already populated
    current_count = collection.count()
    if current_count > 0 and not force_rebuild:
        logger.info(f"Collection '{COLLECTION_NAME}' already contains {current_count} vectors. Skipping re-indexing.")
        return collection

    logger.info(f"Indexing chunks from {CHUNKS_FILE} into ChromaDB...")

    ids = []
    documents = []
    metadatas = []

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            chunk = json.loads(line)

            ids.append(chunk["chunk_id"])
            documents.append(chunk["text"])

            # ChromaDB metadata must be primitive types (str, int, float, bool)
            meta = {
                "doc_id": str(chunk.get("doc_id", "")),
                "source_url": str(chunk.get("source_url", "")),
                "title": str(chunk.get("title", "")),
                "category": str(chunk.get("category", "")),
                "academic_session": str(chunk.get("academic_session", "")),
                "authority_tier": str(chunk.get("authority_tier", "official_primary")),
                "is_stale": bool(chunk.get("is_stale", False)),
                "breadcrumb": str(chunk.get("breadcrumb", "")),
                "token_estimate": int(chunk.get("token_estimate", 0)),
            }
            metadatas.append(meta)

    # Batch add (Chroma handles batches up to 5000 items)
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        b_ids = ids[i:i+batch_size]
        b_docs = documents[i:i+batch_size]
        b_metas = metadatas[i:i+batch_size]
        collection.add(
            ids=b_ids,
            documents=b_docs,
            metadatas=b_metas
        )

    logger.info(f"✓ Successfully indexed {collection.count()} vectors into '{COLLECTION_NAME}'.")
    return collection

def query_vector_store(
    query_text: str,
    top_k: int = 5,
    filter_category: Optional[str] = None,
    official_only: bool = False
) -> Dict[str, Any]:
    """
    Performs vector similarity search with optional metadata filtering.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(COLLECTION_NAME)

    where_clause = {}
    conditions = []
    if official_only:
        conditions.append({"authority_tier": "official_primary"})
    if filter_category:
        conditions.append({"category": filter_category})

    if len(conditions) == 1:
        where_clause = conditions[0]
    elif len(conditions) > 1:
        where_clause = {"$and": conditions}

    results = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where=where_clause if where_clause else None
    )
    return results

if __name__ == "__main__":
    build_vector_index(force_rebuild=True)
