"""
Production Batch Ingestion Pipeline with Anti-Bot Stealth, Poisoning Filter,
and Official Authority Tiering.
"""
import csv
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in sys.path so script can run directly as `python src/...`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CHUNKS_FILE,
    POLITE_DELAY_SEC,
    PROCESSED_MD_DIR,
    PROCESSED_META_DIR,
    RAW_HTML_DIR,
    RAW_PDF_DIR,
    SOURCES_CSV,
)
from src.extractors.html_extractor import extract_html_to_markdown, is_blocked_or_poisoned
from src.extractors.pdf_extractor import extract_pdf_to_markdown
from src.extractors.stealth_downloader import download_stealth
from src.processors.chunker import hierarchical_chunk_markdown
from src.processors.cleaner import compute_content_hash, is_content_poisoned

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("RAGPipeline")

def slugify(text: str) -> str:
    """Create filesystem-safe filename from string."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)[:50]

def infer_academic_session(text: str, notes: str) -> str:
    """Infers academic session from text or notes."""
    combined = f"{text} {notes}"
    match = re.search(r"\b(202\d[-/]\d{2,4})\b", combined)
    if match:
        return match.group(1).replace("/", "-")
    return "General / Unspecified"

def process_source_entry(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Fetches, audits, validates, and extracts a source entry."""
    source_name = row.get("Source", "").strip()
    url = row.get("Link", "").strip()
    category = row.get("Category", "General").strip()
    _fmt = row.get("Format", "").strip().lower()
    what_to_extract = row.get("What to extract", "").strip()
    notes = row.get("Notes", "").strip()

    if not url or not url.startswith("http"):
        logger.warning(f"Skipping empty or invalid URL for: {source_name}")
        return None

    doc_slug = slugify(source_name)
    doc_id = f"{slugify(category)}_{doc_slug}"

    print(f"\n{'='*70}\n[PROCESSING] {source_name} ({category})\nURL: {url}\n{'='*70}")

    # Step 1: Download using Multi-Tier Anti-Bot Stealth Downloader
    download_res = download_stealth(url)
    if not download_res:
        logger.error(f"Failed to download {source_name} after all bypass tiers.")
        return None

    content_bytes, content_type = download_res

    # Robust MIME detection: Magic bytes and Content-Type header
    is_pdf = (
        content_bytes.startswith(b"%PDF") or
        "application/pdf" in content_type.lower() or
        (url.lower().endswith(".pdf") and not content_bytes.strip().startswith(b"<!"))
    )

    academic_session = infer_academic_session(what_to_extract, notes)
    markdown_content = ""
    extractor_info = {}

    try:
        if is_pdf:
            raw_pdf_path = RAW_PDF_DIR / f"{doc_id}.pdf"
            raw_pdf_path.write_bytes(content_bytes)
            logger.info(f"Saved raw PDF: {raw_pdf_path.name} ({len(content_bytes)} bytes)")

            extracted = extract_pdf_to_markdown(raw_pdf_path)
            markdown_content = extracted["markdown"]
            extractor_info = {
                "extractor": extracted.get("extractor"),
                "total_pages": extracted.get("total_pages", 1),
                "tables_found": extracted.get("tables_found", 0)
            }
        else:
            try:
                html_text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    html_text = content_bytes.decode("latin-1")
                except Exception:
                    html_text = content_bytes.decode("utf-8", errors="ignore")

            raw_html_path = RAW_HTML_DIR / f"{doc_id}.html"
            raw_html_path.write_text(html_text, encoding="utf-8")
            logger.info(f"Saved raw HTML: {raw_html_path.name} ({len(html_text)} chars)")

            extracted = extract_html_to_markdown(html_text, url=url)
            markdown_content = extracted["markdown"]
            extractor_info = {
                "extractor": extracted.get("extractor_used"),
                "extracted_title": extracted.get("title"),
                "linked_pdfs": extracted.get("linked_pdfs", [])
            }
    except Exception as e:
        logger.error(f"Error extracting content for {source_name}: {e}")
        return None

    # Step 2: Ingestion Quality Gate (Poisoning & Firewall Block Detection)
    if not markdown_content or len(markdown_content.strip()) < 40:
        logger.warning(f"Extracted content too short for {source_name}. Skipping.")
        return None

    if is_content_poisoned(markdown_content) or is_blocked_or_poisoned(markdown_content):
        logger.error(f"⚠️ QUALITY GATE TRIGGERED: Content from {source_name} is a firewall block or error page! Quarantining to prevent RAG poisoning.")
        return None

    # Step 3: Metadata Enrichment
    doc_metadata = {
        "doc_id": doc_id,
        "source_name": source_name,
        "source_url": url,
        "category": category,
        "doc_type": "pdf" if is_pdf else "html",
        "academic_session": academic_session,
        "what_to_extract": what_to_extract,
        "notes": notes,
        "content_hash": compute_content_hash(markdown_content),
        "extractor_info": extractor_info,
        "char_count": len(markdown_content)
    }

    # Step 4: Save Clean Processed Document & Metadata
    md_file = PROCESSED_MD_DIR / f"{doc_id}.md"
    meta_file = PROCESSED_META_DIR / f"{doc_id}.json"

    frontmatter = (
        f"---\n"
        f"title: \"{source_name}\"\n"
        f"source_url: \"{url}\"\n"
        f"category: \"{category}\"\n"
        f"session: \"{academic_session}\"\n"
        f"doc_type: \"{'pdf' if is_pdf else 'html'}\"\n"
        f"---\n\n"
    )
    md_file.write_text(frontmatter + markdown_content, encoding="utf-8")
    meta_file.write_text(json.dumps(doc_metadata, indent=2), encoding="utf-8")
    logger.info(f"Saved verified clean markdown ({len(markdown_content)} chars): {md_file.name}")

    # Step 5: Hierarchical Semantic Chunking with Breadcrumb Context
    chunks = hierarchical_chunk_markdown(markdown_content, doc_metadata)
    logger.info(f"Generated {len(chunks)} contextual chunks for {source_name}")

    return {
        "metadata": doc_metadata,
        "chunks": chunks
    }

def run_pipeline():
    """Runs the full batch ingestion and quality-assured RAG chunking pipeline."""
    if not SOURCES_CSV.exists():
        logger.error(f"Sources CSV missing at {SOURCES_CSV}")
        return

    logger.info(f"Starting batch extraction pipeline from {SOURCES_CSV}")

    processed_count = 0
    total_chunks = []

    with open(SOURCES_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("Link") or row.get("Link").lower() == "link":
                continue

            result = process_source_entry(row)
            if result:
                processed_count += 1
                total_chunks.extend(result["chunks"])

            time.sleep(POLITE_DELAY_SEC)

    # Save all verified chunks to JSONL
    if total_chunks:
        with open(CHUNKS_FILE, "w", encoding="utf-8") as out_f:
            for chunk in total_chunks:
                out_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Quality Audit Metrics
    official_chunks = sum(1 for c in total_chunks if c.get("authority_tier") == "official_primary")
    secondary_chunks = sum(1 for c in total_chunks if c.get("authority_tier") == "aggregator_secondary")
    fresh_chunks = sum(1 for c in total_chunks if not c.get("is_stale", False))
    stale_chunks = sum(1 for c in total_chunks if c.get("is_stale", False))

    print("\n" + "=" * 75)
    print("SENIOR DEVELOPER QUALITY & COVERAGE AUDIT SUMMARY:")
    print(f"  • Total Valid Documents Processed:          {processed_count}")
    print(f"  • Total High-Quality RAG Chunks:             {len(total_chunks)}")
    print(f"  • Official Primary Chunks (PU / NIC):        {official_chunks} ({official_chunks*100//len(total_chunks)}%)")
    print(f"  • Aggregator Secondary Chunks:              {secondary_chunks} ({secondary_chunks*100//len(total_chunks)}%)")
    print(f"  • Fresh / Valid Session Chunks:              {fresh_chunks}")
    print(f"  • Historical Reference Only Chunks:          {stale_chunks}")
    print(f"  • Verified Vector JSONL Destination:        {CHUNKS_FILE}")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    run_pipeline()
