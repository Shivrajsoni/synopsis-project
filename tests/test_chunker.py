"""Tests for Hierarchical Breadcrumb Chunker."""
from src.processors.chunker import hierarchical_chunk_markdown


def test_hierarchical_chunking():
    md = """# University Admissions
Here is an overview of admissions.

## Eligibility Criteria
Candidates must have passed 10+2 examination with Physics and Mathematics.

### Minimum Percentage
Minimum 60% marks in aggregate are required for General Category.

## Fee Structure
The semester fee is INR 50,000 payable at the beginning of each semester.
"""
    doc_meta = {
        "doc_id": "test_doc",
        "source_name": "Test Admissions",
        "source_url": "https://example.com/admissions",
        "category": "Admission",
        "academic_session": "2026-27"
    }

    chunks = hierarchical_chunk_markdown(md, doc_meta)
    assert len(chunks) >= 3

    # Check breadcrumb presence
    breadcrumbs = [c["breadcrumb"] for c in chunks]
    assert any("University Admissions" in b for b in breadcrumbs)
    assert any("Eligibility Criteria" in b for b in breadcrumbs)

    # Check context prefix in text
    for c in chunks:
        assert c["text"].startswith("### Context:")
        assert "source_url" in c
