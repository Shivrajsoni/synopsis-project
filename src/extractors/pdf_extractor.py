"""
PDF Document and Table Extractor for University Prospectuses & Fee Notices.
Converts PDFs into structured, Markdown-formatted text with preserved table structures.
"""
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from src.processors.cleaner import clean_markdown_text

logger = logging.getLogger(__name__)

def table_to_markdown(table_data: List[List[Optional[str]]]) -> str:
    """Converts a 2D list of table cells into clean GitHub-flavored Markdown."""
    if not table_data or len(table_data) < 1:
        return ""

    # Clean cell texts
    cleaned_rows = []
    for row in table_data:
        cleaned_row = [
            (str(cell).strip().replace("\n", " ").replace("|", "\\|") if cell is not None else "")
            for cell in row
        ]
        # Only keep rows that have at least one non-empty cell
        if any(cleaned_row):
            cleaned_rows.append(cleaned_row)

    if not cleaned_rows:
        return ""

    num_cols = max(len(row) for row in cleaned_rows)
    # Pad rows to have uniform column count
    for i, row in enumerate(cleaned_rows):
        if len(row) < num_cols:
            cleaned_rows[i] = row + [""] * (num_cols - len(row))

    # Header row
    header = cleaned_rows[0]
    separator = ["---"] * num_cols

    md_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |"
    ]

    # Data rows
    for row in cleaned_rows[1:]:
        md_lines.append("| " + " | ".join(row) + " |")

    return "\n" + "\n".join(md_lines) + "\n"

def extract_pdf_with_pdfplumber(pdf_path_or_bytes) -> Dict[str, Any]:
    """
    Extracts text and tables using pdfplumber, converting tables to markdown grids.
    Preserves spatial layout and prevents table distortion.
    """
    all_pages_content = []
    table_count = 0

    target = pdf_path_or_bytes if isinstance(pdf_path_or_bytes, (str, Path)) else io.BytesIO(pdf_path_or_bytes)

    with pdfplumber.open(target) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages):
            page_num = page_idx + 1
            page_text_blocks = []

            # Step 1: Detect and extract tables
            tables = page.find_tables()
            table_bboxes = []

            if tables:
                for table in tables:
                    table_bboxes.append(table.bbox)
                    raw_table = table.extract()
                    md_table = table_to_markdown(raw_table)
                    if md_table:
                        table_count += 1
                        page_text_blocks.append(f"\n#### [Table: Page {page_num}]\n{md_table}\n")

            # Step 2: Extract text outside the detected tables
            # If no tables were detected, extract entire page text
            if not table_bboxes:
                page_text = page.extract_text(layout=False) or ""
            else:
                # Filter out table bounding boxes to avoid duplicate text
                try:
                    non_table_page = page
                    for bbox in table_bboxes:
                        non_table_page = non_table_page.filter(
                            lambda obj, b=bbox: not (
                                obj["x0"] >= b[0] and obj["x1"] <= b[2] and
                                obj["top"] >= b[1] and obj["bottom"] <= b[3]
                            )
                        )
                    page_text = non_table_page.extract_text() or ""
                except Exception:
                    page_text = page.extract_text() or ""

            page_header = f"\n\n### Page {page_num}\n"
            full_page = page_header + page_text.strip() + "\n" + "\n".join(page_text_blocks)
            all_pages_content.append(full_page)

    full_markdown = "\n".join(all_pages_content)
    return {
        "markdown": clean_markdown_text(full_markdown),
        "total_pages": total_pages,
        "tables_found": table_count,
        "extractor": "pdfplumber"
    }

def extract_pdf_with_pypdf(pdf_path_or_bytes) -> Dict[str, Any]:
    """Fallback text extractor using PyPDF."""
    target = pdf_path_or_bytes if isinstance(pdf_path_or_bytes, (str, Path)) else io.BytesIO(pdf_path_or_bytes)
    reader = PdfReader(target)
    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_text.append(f"\n### Page {idx + 1}\n" + text.strip())

    full_text = "\n".join(pages_text)
    return {
        "markdown": clean_markdown_text(full_text),
        "total_pages": len(reader.pages),
        "tables_found": 0,
        "extractor": "pypdf"
    }

def extract_pdf_to_markdown(pdf_path_or_bytes) -> Dict[str, Any]:
    """Main entrypoint for PDF extraction with progressive fallbacks."""
    if PDFPLUMBER_AVAILABLE:
        try:
            return extract_pdf_with_pdfplumber(pdf_path_or_bytes)
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}. Trying fallback...")

    if PYMUPDF_AVAILABLE:
        try:
            doc = pymupdf.open(pdf_path_or_bytes)
            pages_text = []
            for idx, page in enumerate(doc):
                text = page.get_text() or ""
                pages_text.append(f"\n### Page {idx + 1}\n" + text.strip())
            return {
                "markdown": clean_markdown_text("\n".join(pages_text)),
                "total_pages": len(doc),
                "tables_found": 0,
                "extractor": "pymupdf"
            }
        except Exception as e:
            logger.warning(f"pymupdf fallback failed: {e}. Trying pypdf...")

    if PYPDF_AVAILABLE:
        try:
            return extract_pdf_with_pypdf(pdf_path_or_bytes)
        except Exception as e:
            logger.warning(f"pypdf fallback failed: {e}")

    return {
        "markdown": "",
        "total_pages": 0,
        "tables_found": 0,
        "extractor": "failed"
    }
