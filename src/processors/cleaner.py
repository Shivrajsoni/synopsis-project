"""
Text cleaning, normalization, and quality validation utilities for RAG ingestion.
"""
import hashlib
import re
import unicodedata

# Firewall & Block Signatures to guard against poisoned chunks
POISON_PATTERNS = [
    r"web page blocked",
    r"violation of panjab university it usage policy",
    r"globalurl\.fortinet\.net",
    r"malicious websites",
    r"access denied",
    r"403 forbidden",
    r"attention required! \| cloudflare",
    r"error 404\b",
    r"page not found",
]

def is_content_poisoned(text: str) -> bool:
    """Detects whether extracted content is a firewall block or error page."""
    text_lower = text.lower()
    for pattern in POISON_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def normalize_unicode(text: str) -> str:
    """Normalize unicode characters, smart quotes, and strange dashes."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("—", " - ").replace("–", " - ")
    return text

def clean_markdown_text(text: str) -> str:
    """
    Cleans extracted markdown text:
    - Normalizes unicode
    - Removes duplicate consecutive newlines
    - Strips UI noise
    """
    if not text:
        return ""

    text = normalize_unicode(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())

    boilerplate_patterns = [
        r"Skip to (main )?content",
        r"Screen Reader Access",
        r"A\+\s+A\s+A\-",
        r"Feedback\s+\|\s+Contact Us",
        r"Copyright\s+©?\s*\d{4}.*Panjab University.*All [Rr]ights [Rr]eserved\.?",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()

def compute_content_hash(text: str) -> str:
    """Computes a SHA-256 hash of the cleaned text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
