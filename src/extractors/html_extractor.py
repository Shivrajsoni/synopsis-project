"""
HTML and Web Page Extractor for University Portals.
Combines domain-specific structural parsing (preserving announcement tables & circulars)
with Trafilatura main-text extraction and BeautifulSoup fallback.
"""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from src.processors.cleaner import clean_markdown_text

logger = logging.getLogger(__name__)

# Known blocked / firewall signatures to guard against data poisoning
BLOCKED_SIGNATURES = [
    "web page blocked",
    "violation of panjab university it usage policy",
    "fortinet",
    "access denied",
    "403 forbidden",
    "attention required! | cloudflare",
    "just a moment...",
    "enable javascript and cookies to continue",
]

def is_blocked_or_poisoned(text: str) -> bool:
    """Checks if the extracted text is an error/firewall block page."""
    text_lower = text.lower()
    return any(sig in text_lower for sig in BLOCKED_SIGNATURES)

def extract_university_portal_content(soup: BeautifulSoup, base_url: str = "") -> Optional[str]:
    """
    Specifically targets Panjab University and government portal content containers
    (#inhalt, .termine, main, article, #content) to ensure notice tables, circular links,
    and scholarship lists are NEVER discarded by statistical heuristics.
    """
    # Look for PU / UIET primary content blocks
    container = (
        soup.find("div", {"id": "inhalt"}) or
        soup.find("div", {"class": "innen"}) or
        soup.find("div", {"id": "content"}) or
        soup.find("main") or
        soup.find("article")
    )
    if not container:
        return None

    # Resolve relative links to absolute URLs so RAG chunks contain valid citation links
    if base_url:
        for a_tag in container.find_all("a", href=True):
            a_tag["href"] = urljoin(base_url, a_tag["href"])

    # Convert container to clean Markdown
    md_content = md(
        str(container),
        heading_style="ATX",
        strip=["script", "style", "noscript", "svg"]
    )
    return clean_markdown_text(md_content)

def extract_html_to_markdown(html_content: str, url: str = "") -> Dict[str, Any]:
    """
    Extracts structured markdown and metadata from raw HTML.

    Returns:
        dict: {
            "title": str,
            "markdown": str,
            "extractor_used": str,
            "character_count": int,
            "is_valid": bool,
            "linked_pdfs": list
        }
    """
    title = ""
    markdown_content = ""
    extractor_used = "none"
    linked_pdfs = []

    soup = None
    if BS4_AVAILABLE:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title = title_tag.string.strip()

            # Discover high-value PDFs linked on this page
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                link_text = a_tag.get_text().strip()
                if href.lower().endswith(".pdf") or "pdf" in href.lower():
                    abs_url = urljoin(url, href) if url else href
                    if abs_url.startswith("http") and link_text:
                        linked_pdfs.append({"title": link_text, "url": abs_url})
        except Exception as e:
            logger.warning(f"BS4 parsing error: {e}")

    # Strategy 1: Targeted University Portal Container
    if soup:
        portal_md = extract_university_portal_content(soup, base_url=url)
        # If the container has substantial notices or lists (> 200 chars), prioritize it!
        if portal_md and len(portal_md) > 200:
            markdown_content = portal_md
            extractor_used = "targeted_portal_container"

    # Strategy 2: Trafilatura (SOTA for long-form prose and standard articles)
    if not markdown_content and TRAFILATURA_AVAILABLE:
        try:
            extracted = trafilatura.extract(
                html_content,
                url=url,
                output_format="markdown",
                include_links=True,
                include_tables=True,
                favor_recall=True,
                deduplicate=True
            )
            if extracted and len(extracted.strip()) > 100:
                markdown_content = extracted
                extractor_used = "trafilatura"
        except Exception as e:
            logger.warning(f"Trafilatura failed for {url}: {e}")

    # Strategy 3: BeautifulSoup fallback
    if not markdown_content and soup:
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        body = soup.body or soup
        raw_md = md(str(body), heading_style="ATX")
        markdown_content = clean_markdown_text(raw_md)
        extractor_used = "bs4_fallback"

    cleaned_md = clean_markdown_text(markdown_content)
    is_valid = bool(cleaned_md and not is_blocked_or_poisoned(cleaned_md))

    return {
        "title": title or "Panjab University Webpage",
        "markdown": cleaned_md,
        "extractor_used": extractor_used,
        "character_count": len(cleaned_md),
        "is_valid": is_valid,
        "linked_pdfs": linked_pdfs
    }
