"""
Hierarchical Markdown-Aware Semantic Chunker for University RAG.
Maintains heading hierarchy (breadcrumbs), preserves markdown tables intact,
and enriches chunks with authority tiers (official vs aggregator) and staleness flags.
"""
import hashlib
import re
from typing import Any, Dict, List


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 characters per token for English)."""
    return max(1, len(text) // 4)

def determine_authority_tier(url: str) -> str:
    """Classifies source authority for RAG prioritization."""
    url_lower = url.lower()
    if "puchd.ac.in" in url_lower or "admissions.nic.in" in url_lower:
        return "official_primary"
    return "aggregator_secondary"

def determine_staleness(session: str, notes: str) -> bool:
    """Detects whether information is outdated or historical reference only."""
    notes_lower = notes.lower()
    if "outdated" in notes_lower or "historical" in notes_lower:
        return True
    match = re.search(r"20(1\d|2[0-3])", session)
    if match:
        return True
    return False

def split_large_text(text: str, max_chars: int = 2400) -> List[str]:
    """Splits text exceeding maximum size by paragraphs."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > max_chars and current_chunk:
            chunk_str = "\n\n".join(current_chunk).strip()
            if chunk_str:
                chunks.append(chunk_str)
            current_chunk = [para]
            current_len = para_len
        else:
            current_chunk.append(para)
            current_len += para_len + 2

    if current_chunk:
        chunk_str = "\n\n".join(current_chunk).strip()
        if chunk_str:
            chunks.append(chunk_str)

    return chunks

def hierarchical_chunk_markdown(
    markdown_text: str,
    metadata: Dict[str, Any],
    target_chunk_chars: int = 2400
) -> List[Dict[str, Any]]:
    """
    Splits markdown by headings (#, ##, ###, ####), tracks the heading breadcrumb stack,
    and prepends the breadcrumb context to each chunk.
    """
    lines = markdown_text.splitlines()
    sections = []

    current_headers = {1: metadata.get("title", "Document"), 2: "", 3: "", 4: ""}
    current_buffer = []

    def get_breadcrumb() -> str:
        parts = [current_headers[lvl] for lvl in sorted(current_headers.keys()) if current_headers[lvl]]
        return " > ".join(parts)

    for line in lines:
        header_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if header_match:
            if current_buffer:
                content = "\n".join(current_buffer).strip()
                if content:
                    sections.append({
                        "breadcrumb": get_breadcrumb(),
                        "content": content
                    })
                current_buffer = []

            level = len(header_match.group(1))
            heading_text = header_match.group(2).strip()
            current_headers[level] = heading_text
            for h_lvl in range(level + 1, 5):
                current_headers[h_lvl] = ""
        else:
            current_buffer.append(line)

    if current_buffer:
        content = "\n".join(current_buffer).strip()
        if content:
            sections.append({
                "breadcrumb": get_breadcrumb(),
                "content": content
            })

    if not sections and markdown_text.strip():
        sections.append({
            "breadcrumb": metadata.get("title", "Document"),
            "content": markdown_text.strip()
        })

    rag_chunks = []
    doc_id = metadata.get("doc_id", "doc_unknown")
    source_url = metadata.get("source_url", "")
    session_str = metadata.get("academic_session", "General")
    notes_str = metadata.get("notes", "")

    authority_tier = determine_authority_tier(source_url)
    is_stale = determine_staleness(session_str, notes_str)

    for sec_idx, sec in enumerate(sections):
        sec_content = sec["content"]
        breadcrumb = sec["breadcrumb"]

        if len(sec_content) <= target_chunk_chars:
            sub_pieces = [sec_content]
        else:
            sub_pieces = split_large_text(sec_content, max_chars=target_chunk_chars)

        for p_idx, piece in enumerate(sub_pieces):
            enriched_content = f"### Context: [{breadcrumb}]\n\n{piece}"
            chunk_hash = hashlib.sha256(enriched_content.encode("utf-8")).hexdigest()[:12]

            chunk_record = {
                "chunk_id": f"{doc_id}_c{sec_idx}_{p_idx}_{chunk_hash}",
                "doc_id": doc_id,
                "source_url": source_url,
                "title": metadata.get("title", ""),
                "category": metadata.get("category", "General"),
                "academic_session": session_str,
                "authority_tier": authority_tier,
                "is_stale": is_stale,
                "breadcrumb": breadcrumb,
                "token_estimate": estimate_tokens(enriched_content),
                "text": enriched_content,
                "raw_section_text": piece,
                "metadata": metadata
            }
            rag_chunks.append(chunk_record)

    return rag_chunks
