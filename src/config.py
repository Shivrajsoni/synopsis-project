"""
Configuration settings for the University Chatbot Data Pipeline.
"""
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"
RAW_HTML_DIR = RAW_DIR / "html"
RAW_PDF_DIR = RAW_DIR / "pdf"

PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_MD_DIR = PROCESSED_DIR / "markdown"
PROCESSED_META_DIR = PROCESSED_DIR / "metadata"

CHUNKS_DIR = DATA_DIR / "chunks"
CHUNKS_FILE = CHUNKS_DIR / "rag_chunks.jsonl"
SOURCES_CSV = DATA_DIR / "sources.csv"

# Scraper Settings
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (Academic Research Bot - PU Synopsis)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT_SEC = 25
POLITE_DELAY_SEC = 1.5  # Polite delay between web requests to respect university servers

# Chunking Settings for RAG
TARGET_CHUNK_SIZE = 600   # Approximate tokens (~2400 chars)
CHUNK_OVERLAP = 100       # Approximate tokens (~400 chars)
MAX_CHUNK_SIZE = 1000     # Hard ceiling for large sections
