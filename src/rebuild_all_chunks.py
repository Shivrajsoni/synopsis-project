"""
Full Re-chunker and Vector DB Rebuilder.
Reads all processed markdown files in data/processed/markdown,
generates hierarchical contextual chunks with injected breadcrumbs,
updates data/chunks/rag_chunks.jsonl, and rebuilds the persistent ChromaDB collection.
"""
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path so script can run directly as `python src/...`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CHUNKS_FILE, PROCESSED_MD_DIR
from src.processors.chunker import hierarchical_chunk_markdown
from src.vector_store import build_vector_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Rebuilder")

def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Extracts yaml frontmatter and body text from markdown."""
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    meta[k] = v
    return meta, body

def rebuild_all():
    md_files = sorted(list(PROCESSED_MD_DIR.glob("*.md")))
    logger.info(f"Found {len(md_files)} markdown files in {PROCESSED_MD_DIR}")

    all_chunks: List[Dict[str, Any]] = []
    seen_chunk_ids = set()

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)

        doc_id = md_file.stem
        source_url = meta.get("source_url", "https://puchd.ac.in")
        category = meta.get("category", "General")
        session = meta.get("session", "2026-27")
        title = meta.get("title", doc_id.replace("_", " ").title())

        doc_meta = {
            "doc_id": doc_id,
            "source_name": title,
            "source_url": source_url,
            "category": category,
            "academic_session": session,
            "notes": meta.get("notes", ""),
            "what_to_extract": title
        }

        chunks = hierarchical_chunk_markdown(body, doc_meta)
        for c in chunks:
            cid = c["chunk_id"]
            if cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                all_chunks.append(c)

    logger.info(f"Generated total {len(all_chunks)} unique contextual chunks.")

    # Write to rag_chunks.jsonl
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    logger.info(f"Successfully saved {len(all_chunks)} chunks to {CHUNKS_FILE}")

    # Rebuild ChromaDB
    logger.info("Rebuilding persistent ChromaDB vector store...")
    build_vector_index(force_rebuild=True)
    logger.info("ChromaDB vector store rebuilding complete!")

if __name__ == "__main__":
    rebuild_all()
