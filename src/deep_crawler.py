"""
Multi-Perspective Recursive Deep Crawler for Panjab University & UIET.
Crawls multi-level internal pages and deeply linked PDFs across 6 student perspectives:
1. Undergraduate Admissions & JAC Counselling
2. Postgraduate & Ph.D. Admissions
3. Lateral Entry & Migration (PULEET/PUMEET)
4. Engineering Departments, Syllabi & Curriculum Schemes
5. Campus Life, Hostels, Sports & Regulations
6. Training & Placement Cell (TPO) Statistics & Procedures
"""
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

# Ensure project root is in sys.path so script can run directly as `python src/...`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup

from src.config import CHUNKS_FILE, POLITE_DELAY_SEC, PROCESSED_MD_DIR, PROCESSED_META_DIR, RAW_HTML_DIR, RAW_PDF_DIR
from src.extractors.html_extractor import extract_html_to_markdown, is_blocked_or_poisoned
from src.extractors.pdf_extractor import extract_pdf_to_markdown
from src.extractors.stealth_downloader import download_stealth
from src.processors.chunker import hierarchical_chunk_markdown
from src.processors.cleaner import compute_content_hash, is_content_poisoned
from src.vector_store import build_vector_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DeepCrawler")

# High-Value Multi-Perspective Seed URLs
PERSPECTIVE_SEEDS = [
    # Perspective 1: UG Admissions & Entrance Tests
    {"url": "https://jacchd.admissions.nic.in", "category": "Admissions_UG", "perspective": "UG Admissions & Counselling"},
    {"url": "https://cetug.puchd.ac.in", "category": "Admissions_UG", "perspective": "CET-UG Entrance"},
    {"url": "https://uglaw.puchd.ac.in", "category": "Admissions_UG", "perspective": "UG Law Entrance"},
    {"url": "https://puthat.puchd.ac.in", "category": "Admissions_UG", "perspective": "PUTHAT Hotel Management"},
    {"url": "https://uiet.puchd.ac.in/?page_id=5555", "category": "Admissions_UG", "perspective": "UIET B.E. Admissions"},

    # Perspective 2: PG & Ph.D. Admissions
    {"url": "https://cetpg.puchd.ac.in", "category": "Admissions_PG", "perspective": "CET-PG Entrance"},
    {"url": "https://phdengineering.puchd.ac.in", "category": "Admissions_PhD", "perspective": "Ph.D. Engineering Admissions"},
    {"url": "https://met.puchd.ac.in", "category": "Admissions_PG", "perspective": "PU-MET Sectoral MBA"},
    {"url": "https://pglaw.puchd.ac.in", "category": "Admissions_PG", "perspective": "PG Law 3-Year LLB"},

    # Perspective 3: Lateral Entry & Migration
    {"url": "https://puleet.puchd.ac.in", "category": "Lateral_Entry", "perspective": "PULEET B.E. 2nd Year Lateral Entry"},
    {"url": "https://pumeet.puchd.ac.in", "category": "Lateral_Entry", "perspective": "PUMEET 1st Year B.E. Migration"},

    # Perspective 4: UIET Engineering Departments & Syllabi
    {"url": "https://uiet.puchd.ac.in/?page_id=46", "category": "UIET_Departments", "perspective": "Computer Science & Engineering"},
    {"url": "https://uiet.puchd.ac.in/?page_id=5931", "category": "UIET_Syllabus", "perspective": "CSE Curriculum & Scheme"},
    {"url": "https://uiet.puchd.ac.in/?page_id=7", "category": "UIET_Departments", "perspective": "Information Technology"},
    {"url": "https://uiet.puchd.ac.in/?page_id=212", "category": "UIET_Departments", "perspective": "Electronics & Communication Engineering"},
    {"url": "https://uiet.puchd.ac.in/?page_id=3234", "category": "UIET_Syllabus", "perspective": "ECE Curriculum & Scheme"},
    {"url": "https://uiet.puchd.ac.in/?page_id=444", "category": "UIET_Departments", "perspective": "Mechanical Engineering"},
    {"url": "https://uiet.puchd.ac.in/?page_id=13990", "category": "UIET_Syllabus", "perspective": "Mechanical Curriculum & Scheme"},
    {"url": "https://uiet.puchd.ac.in/?page_id=353", "category": "UIET_Departments", "perspective": "Electrical & Electronics Engineering"},
    {"url": "https://uiet.puchd.ac.in/?page_id=480", "category": "UIET_Departments", "perspective": "Applied Sciences Department"},
    {"url": "https://uiet.puchd.ac.in/?page_id=3128", "category": "UIET_Academics", "perspective": "B.E. 1st Year Induction & Batch Guide"},

    # Perspective 5: Campus Life, Hostels, Sports & Rules
    {"url": "https://hostels.puchd.ac.in", "category": "Campus_Life", "perspective": "Panjab University Hostels & Residence Halls"},
    {"url": "https://sports.puchd.ac.in", "category": "Campus_Life", "perspective": "Campus Sports & Gym Facilities"},
    {"url": "https://library.puchd.ac.in", "category": "Campus_Life", "perspective": "Central & UIET Library Facilities"},
    {"url": "https://uiet.puchd.ac.in/?page_id=14006", "category": "Campus_Rules", "perspective": "Anti-Ragging Regulations & Undertaking"},
    {"url": "https://uiet.puchd.ac.in/?page_id=1950", "category": "Campus_Rules", "perspective": "Student Grievance Redressal Cell"},

    # Perspective 6: Training & Placement Cell (TPO)
    {"url": "https://uiet.puchd.ac.in/?page_id=323", "category": "UIET_Placements", "perspective": "UIET Placements Overview"},
    {"url": "https://uiet.puchd.ac.in/?page_id=329", "category": "UIET_Placements", "perspective": "Campus Placements Recruitment Procedure"},
]

KEYWORD_FILTER = re.compile(
    r"(admission|prospectus|syllabus|scheme|fee|hostel|scholarship|placement|counselling|cutoff|seat|rule|notice|calendar|puleet|pumeet|cet|handbook|guideline|eligib|important|dates)",
    re.IGNORECASE
)

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)[:55]

def is_allowed_domain(url: str) -> bool:
    """Restricts crawling to official university and government domains."""
    try:
        domain = urlparse(url).netloc.lower()
        allowed = ["puchd.ac.in", "admissions.nic.in", "gov.in"]
        return any(d in domain for d in allowed)
    except Exception:
        return False

def extract_child_links(html_text: str, base_url: str) -> List[Dict[str, str]]:
    """Discovers internal HTML pages and PDF links."""
    soup = BeautifulSoup(html_text, "html.parser")
    discovered = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        link_text = a.get_text().strip()
        if not href or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        abs_url = urljoin(base_url, href)
        clean_url = abs_url.split("#")[0]  # Remove fragment

        if clean_url in seen:
            continue
        seen.add(clean_url)

        if not is_allowed_domain(clean_url):
            continue

        # Check if PDF or relevant HTML link
        is_pdf = clean_url.lower().endswith(".pdf") or "pdf" in clean_url.lower()
        is_relevant = KEYWORD_FILTER.search(clean_url) or KEYWORD_FILTER.search(link_text) or "page_id" in clean_url

        if is_pdf or is_relevant:
            discovered.append({
                "url": clean_url,
                "title": link_text if link_text else "University Document",
                "is_pdf": is_pdf
            })

    return discovered

class DeepCrawler:
    def __init__(self, max_pages: int = 40):
        self.max_pages = max_pages
        self.visited_urls: Set[str] = set()
        self.new_chunks: List[Dict[str, Any]] = []
        self.processed_docs = 0

    def process_document(self, url: str, title: str, category: str, perspective: str, is_pdf: bool) -> Optional[List[Dict[str, Any]]]:
        """Downloads, validates, extracts, and chunks a single document."""
        if url in self.visited_urls:
            return None
        self.visited_urls.add(url)

        doc_slug = slugify(title if title else url)
        doc_id = f"{slugify(category)}_{doc_slug}"

        print(f"\n[{self.processed_docs + 1}/{self.max_pages}] Fetching ({perspective}):\n  URL: {url}")
        res = download_stealth(url, timeout=15)
        if not res:
            return None

        content_bytes, content_type = res
        # Validate MIME
        actual_is_pdf = (
            content_bytes.startswith(b"%PDF") or
            "application/pdf" in content_type.lower() or
            is_pdf
        )

        markdown_content = ""
        extractor_info = {}

        try:
            if actual_is_pdf:
                raw_pdf_path = RAW_PDF_DIR / f"{doc_id}.pdf"
                raw_pdf_path.write_bytes(content_bytes)
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
            logger.error(f"Extraction error on {url}: {e}")
            return None

        if not markdown_content or len(markdown_content.strip()) < 50:
            return None

        if is_content_poisoned(markdown_content) or is_blocked_or_poisoned(markdown_content):
            logger.warning(f"Poisoning gate blocked: {url}")
            return None

        doc_meta = {
            "doc_id": doc_id,
            "source_name": title,
            "source_url": url,
            "category": category,
            "perspective": perspective,
            "doc_type": "pdf" if actual_is_pdf else "html",
            "academic_session": "2026-27",
            "content_hash": compute_content_hash(markdown_content),
            "extractor_info": extractor_info,
            "char_count": len(markdown_content)
        }

        # Save processed files
        md_file = PROCESSED_MD_DIR / f"{doc_id}.md"
        meta_file = PROCESSED_META_DIR / f"{doc_id}.json"
        frontmatter = (
            f"---\n"
            f"title: \"{title}\"\n"
            f"source_url: \"{url}\"\n"
            f"category: \"{category}\"\n"
            f"perspective: \"{perspective}\"\n"
            f"session: \"2026-27\"\n"
            f"---\n\n"
        )
        md_file.write_text(frontmatter + markdown_content, encoding="utf-8")
        meta_file.write_text(json.dumps(doc_meta, indent=2), encoding="utf-8")

        chunks = hierarchical_chunk_markdown(markdown_content, doc_meta)
        logger.info(f"  ✓ Extracted {len(markdown_content)} chars -> Generated {len(chunks)} contextual chunks.")
        self.processed_docs += 1

        # Discover child links if this was an HTML page
        child_links = []
        if not actual_is_pdf:
            child_links = extract_child_links(content_bytes.decode("utf-8", errors="ignore"), base_url=url)

        return chunks, child_links

    def run(self):
        """Executes multi-perspective breadth-first crawling."""
        logger.info("Initializing Multi-Perspective Recursive Crawler...")
        queue = []
        for seed in PERSPECTIVE_SEEDS:
            queue.append({
                "url": seed["url"],
                "title": seed["perspective"],
                "category": seed["category"],
                "perspective": seed["perspective"],
                "is_pdf": False,
                "depth": 0
            })

        while queue and self.processed_docs < self.max_pages:
            item = queue.pop(0)
            url = item["url"]
            depth = item["depth"]

            result = self.process_document(
                url=url,
                title=item["title"],
                category=item["category"],
                perspective=item["perspective"],
                is_pdf=item["is_pdf"]
            )

            if result:
                chunks, child_links = result
                self.new_chunks.extend(chunks)

                # Add child links if within depth limit
                if depth < 1 and child_links:
                    for cl in child_links:
                        if cl["url"] not in self.visited_urls and len(queue) < 60:
                            queue.append({
                                "url": cl["url"],
                                "title": cl["title"],
                                "category": item["category"],
                                "perspective": item["perspective"],
                                "is_pdf": cl["is_pdf"],
                                "depth": depth + 1
                            })

            time.sleep(POLITE_DELAY_SEC)

        # Write to JSONL
        if self.new_chunks:
            existing_ids = set()
            if CHUNKS_FILE.exists():
                with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            existing_ids.add(json.loads(line).get("chunk_id"))

            added = 0
            with open(CHUNKS_FILE, "a", encoding="utf-8") as f:
                for c in self.new_chunks:
                    if c["chunk_id"] not in existing_ids:
                        f.write(json.dumps(c, ensure_ascii=False) + "\n")
                        existing_ids.add(c["chunk_id"])
                        added += 1

            logger.info(f"✓ Appended {added} new unique chunks to {CHUNKS_FILE}.")
            logger.info("Rebuilding ChromaDB Vector Index...")
            build_vector_index(force_rebuild=True)

        print("\n" + "=" * 70)
        print("MULTI-PERSPECTIVE DEEP CRAWL SUMMARY:")
        print(f"  • Total Documents Processed:        {self.processed_docs}")
        print(f"  • Total New Chunks Added:            {len(self.new_chunks)}")
        print(f"  • Total Chunks in Database:          {len(existing_ids) if self.new_chunks else 'N/A'}")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    crawler = DeepCrawler(max_pages=35)
    crawler.run()
