"""
Deep Harvester for Panjab University & UIET.
Systematically crawls specific high-value UIET pages and official Handbook of Information PDFs,
extracting them into structured Markdown, enriching metadata, and generating RAG chunks.
"""
import json
import logging
import re
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path so script can be run directly as `python src/deep_harvester.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CHUNKS_FILE, POLITE_DELAY_SEC, PROCESSED_MD_DIR, PROCESSED_META_DIR, RAW_HTML_DIR, RAW_PDF_DIR
from src.extractors.html_extractor import extract_html_to_markdown, is_blocked_or_poisoned
from src.extractors.pdf_extractor import extract_pdf_to_markdown
from src.extractors.stealth_downloader import download_stealth
from src.processors.chunker import hierarchical_chunk_markdown
from src.processors.cleaner import compute_content_hash, is_content_poisoned
from src.vector_store import build_vector_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DeepHarvester")

# High-Value UIET Specific Pages and Handbook PDFs
EXPANDED_SOURCES = [
    # UIET Admissions & Programmes
    {
        "Source": "UIET B.E. Admissions 2026-27",
        "Link": "https://uiet.puchd.ac.in/?page_id=5555",
        "What to extract": "Official B.E. admission procedure, eligibility, seats for 2026-27",
        "Category": "UIET Admissions",
        "Format": "Web page",
        "Notes": "Official UIET primary page"
    },
    {
        "Source": "UIET M.E./M.Tech Admissions 2026-27",
        "Link": "https://uiet.puchd.ac.in/?page_id=105",
        "What to extract": "M.E. and M.Tech branch specializations, GATE requirements, eligibility",
        "Category": "UIET Admissions",
        "Format": "Web page",
        "Notes": "Official UIET M.Tech details"
    },
    {
        "Source": "UIET PULEET Lateral Entry 2026",
        "Link": "https://uiet.puchd.ac.in/?page_id=5943",
        "What to extract": "PULEET entrance test rules, 2nd year B.E. lateral entry eligibility",
        "Category": "UIET Admissions",
        "Format": "Web page",
        "Notes": "Official UIET lateral entry"
    },
    {
        "Source": "UIET PUMEET Migration 2026",
        "Link": "https://uiet.puchd.ac.in/?page_id=4042",
        "What to extract": "PUMEET migration rules from 1st year B.E.",
        "Category": "UIET Admissions",
        "Format": "Web page",
        "Notes": "Official UIET migration details"
    },
    # UIET Placements & Statistics
    {
        "Source": "UIET Placement Statistics & Past Recruiters",
        "Link": "https://uiet.puchd.ac.in/?page_id=2769",
        "What to extract": "Detailed placement packages, recruiting companies, branch-wise offers",
        "Category": "UIET Placements",
        "Format": "Web page",
        "Notes": "Official UIET TPO statistics"
    },
    # UIET Scholarships
    {
        "Source": "UIET Scholarships & Financial Aid",
        "Link": "https://uiet.puchd.ac.in/?page_id=4229",
        "What to extract": "Merit scholarships, fee concessions, student financial aid at UIET",
        "Category": "Scholarship",
        "Format": "Web page",
        "Notes": "Official UIET scholarship page"
    },
    {
        "Source": "UIET Shraman Foundation Scholarship",
        "Link": "https://uiet.puchd.ac.in/?page_id=8991",
        "What to extract": "Shraman Foundation scholarship eligibility and grant amounts",
        "Category": "Scholarship",
        "Format": "Web page",
        "Notes": "UIET engineering scholarship"
    },
    # UIET Academic Rules & Notices
    {
        "Source": "UIET Attendance Rules & Academic Policy",
        "Link": "https://uiet.puchd.ac.in/?page_id=15173",
        "What to extract": "Attendance criteria (75% rule), condonation rules, medical leaves",
        "Category": "UIET Academics",
        "Format": "Web page",
        "Notes": "Official academic regulations"
    },
    {
        "Source": "UIET Latest News & Notices Board",
        "Link": "https://uiet.puchd.ac.in/?page_id=5797",
        "What to extract": "Current student notices, exam announcements, department circulars",
        "Category": "UIET Notices",
        "Format": "Web page",
        "Notes": "Active notice board"
    },
    {
        "Source": "UIET 1st Year Engineering Syllabus",
        "Link": "https://uiet.puchd.ac.in/?page_id=490",
        "What to extract": "Curriculum, subjects, scheme of examination for first year B.E.",
        "Category": "UIET Academics",
        "Format": "Web page",
        "Notes": "Official syllabus scheme"
    },
    # High-Value Official Handbook of Information 2026-27 PDFs
    {
        "Source": "Handbook 2026-27 Faculty of Engineering & Technology",
        "Link": "https://admissions.puchd.ac.in/includes/documents/2026/hbi-2026-faculty-of-engineering.pdf",
        "What to extract": "Comprehensive UIET & UICET departments, faculty, seat matrix, fees, courses",
        "Category": "Official Handbook",
        "Format": "PDF",
        "Notes": "Core authoritative engineering handbook 2026-27"
    },
    {
        "Source": "Handbook 2026-27 Part A Campus Profile & General Rules",
        "Link": "https://admissions.puchd.ac.in/includes/documents/2026/hbi-2026-part-a-front-pages.pdf",
        "What to extract": "Panjab University general rules, fee refund policy, reservation quotas",
        "Category": "Official Handbook",
        "Format": "PDF",
        "Notes": "General university regulations 2026-27"
    },
    {
        "Source": "Handbook 2026-27 Faculty of Business Management",
        "Link": "https://admissions.puchd.ac.in/includes/documents/2026/hbi-2026-faculty-of-business.pdf",
        "What to extract": "UBS and UIAMS MBA programs, fee structure, eligibility criteria",
        "Category": "Official Handbook",
        "Format": "PDF",
        "Notes": "Official business handbook 2026-27"
    },
    {
        "Source": "PU Lateral Entry & Migration Rules",
        "Link": "https://admissions.puchd.ac.in/migration-lateral-entry.pdf",
        "What to extract": "Detailed migration criteria between institutes and lateral entry guidelines",
        "Category": "Admission",
        "Format": "PDF",
        "Notes": "Official migration document"
    },
    {
        "Source": "JAC Chandigarh PU Institutes Admission Details",
        "Link": "https://cdnbbsr.s3waas.gov.in/s3dd28e50635038e9cf3a648c2dd17ad0a/uploads/2026/06/202606131144800394.pdf",
        "What to extract": "JAC Chandigarh counselling seat matrix and admission rules for UIET Chandigarh and UIET Hoshiarpur",
        "Category": "Admission",
        "Format": "PDF",
        "Notes": "Official NIC counselling brochure"
    }
]

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)[:50]

def harvest_deep_sources():
    """Fetches all expanded sources, extracts them, and appends to RAG chunks."""
    # Ensure all target storage directories exist
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_MD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_META_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting Deep Harvester for {len(EXPANDED_SOURCES)} high-value university sources...")
    new_chunks = []
    processed_count = 0

    for item in EXPANDED_SOURCES:
        source_name = item["Source"]
        url = item["Link"]
        category = item["Category"]
        what_to_extract = item["What to extract"]
        notes = item["Notes"]
        doc_slug = slugify(source_name)
        doc_id = f"{slugify(category)}_{doc_slug}"

        print(f"\n{'='*70}\n[HARVESTING] {source_name}\nURL: {url}\n{'='*70}")
        download_res = download_stealth(url)
        if not download_res:
            logger.warning(f"Could not download {source_name}. Skipping.")
            continue

        content_bytes, content_type = download_res
        content_type_str = (content_type or "").lower()
        is_pdf = (
            content_bytes.startswith(b"%PDF") or
            "application/pdf" in content_type_str or
            url.lower().endswith(".pdf")
        )

        markdown_content = ""
        extractor_info = {}

        try:
            if is_pdf:
                raw_pdf_path = RAW_PDF_DIR / f"{doc_id}.pdf"
                raw_pdf_path.write_bytes(content_bytes)
                logger.info(f"Saved raw PDF: {raw_pdf_path.name} ({len(content_bytes)} bytes)")
                extracted = extract_pdf_to_markdown(raw_pdf_path)
                markdown_content = extracted["markdown"]
                extractor_info = {"extractor": extracted.get("extractor"), "pages": extracted.get("total_pages")}
            else:
                html_text = content_bytes.decode("utf-8", errors="ignore")
                raw_html_path = RAW_HTML_DIR / f"{doc_id}.html"
                raw_html_path.write_text(html_text, encoding="utf-8")
                extracted = extract_html_to_markdown(html_text, url=url)
                markdown_content = extracted["markdown"]
                extractor_info = {"extractor": extracted.get("extractor_used"), "title": extracted.get("title")}
        except Exception as e:
            logger.error(f"Error extracting {source_name}: {e}")
            continue

        if not markdown_content or len(markdown_content.strip()) < 50:
            logger.warning(f"Extracted content too short for {source_name}")
            continue

        if is_content_poisoned(markdown_content) or is_blocked_or_poisoned(markdown_content):
            logger.warning(f"Poisoning gate triggered for {source_name}. Skipping.")
            continue

        doc_metadata = {
            "doc_id": doc_id,
            "source_name": source_name,
            "source_url": url,
            "category": category,
            "doc_type": "pdf" if is_pdf else "html",
            "academic_session": "2026-27",
            "what_to_extract": what_to_extract,
            "notes": notes,
            "content_hash": compute_content_hash(markdown_content),
            "extractor_info": extractor_info,
            "char_count": len(markdown_content)
        }

        # Save processed Markdown and Metadata
        md_file = PROCESSED_MD_DIR / f"{doc_id}.md"
        meta_file = PROCESSED_META_DIR / f"{doc_id}.json"
        frontmatter = (
            f"---\n"
            f"title: \"{source_name}\"\n"
            f"source_url: \"{url}\"\n"
            f"category: \"{category}\"\n"
            f"session: \"2026-27\"\n"
            f"doc_type: \"{'pdf' if is_pdf else 'html'}\"\n"
            f"---\n\n"
        )
        md_file.write_text(frontmatter + markdown_content, encoding="utf-8")
        meta_file.write_text(json.dumps(doc_metadata, indent=2), encoding="utf-8")

        # Chunking
        chunks = hierarchical_chunk_markdown(markdown_content, doc_metadata)
        logger.info(f"Generated {len(chunks)} contextual chunks for {source_name}")
        new_chunks.extend(chunks)
        processed_count += 1
        time.sleep(POLITE_DELAY_SEC)

    # Append to rag_chunks.jsonl avoiding duplicates
    if new_chunks:
        existing_ids = set()
        if CHUNKS_FILE.exists():
            with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        existing_ids.add(json.loads(line).get("chunk_id"))

        added_count = 0
        with open(CHUNKS_FILE, "a", encoding="utf-8") as f:
            for c in new_chunks:
                if c["chunk_id"] not in existing_ids:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
                    existing_ids.add(c["chunk_id"])
                    added_count += 1

        logger.info(f"Added {added_count} brand-new chunks to {CHUNKS_FILE}")

        # Update Vector DB Index
        logger.info("Rebuilding ChromaDB Vector Store with newly harvested documents...")
        build_vector_index(force_rebuild=True)

    print("\n" + "=" * 70)
    print("DEEP HARVEST COMPLETE:")
    print(f"  • New Documents Processed: {processed_count}")
    print(f"  • New Contextual Chunks Generated: {len(new_chunks)}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    harvest_deep_sources()
