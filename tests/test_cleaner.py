"""Tests for cleaner and security filter functions."""
from src.processors.cleaner import clean_markdown_text, compute_content_hash, is_content_poisoned


def test_clean_markdown_text():
    dirty = "Line 1\n\n\n\n\nLine 2\nSkip to main content\nLine 3"
    cleaned = clean_markdown_text(dirty)
    assert "\n\n\n" not in cleaned
    assert "Skip to main content" not in cleaned
    assert "Line 1" in cleaned
    assert "Line 2" in cleaned
    assert "Line 3" in cleaned

def test_compute_content_hash():
    text1 = "Panjab University Chandigarh"
    text2 = "Panjab University Chandigarh"
    text3 = "Different Text"
    h1 = compute_content_hash(text1)
    h2 = compute_content_hash(text2)
    h3 = compute_content_hash(text3)
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16

def test_is_content_poisoned():
    clean_text = "Welcome to UIET Panjab University. Admissions open for session 2026-27."
    assert not is_content_poisoned(clean_text)

    poisoned_text = "Attention: Cloudflare Ray ID: 403 Forbidden. Access Denied. Verify you are human."
    assert is_content_poisoned(poisoned_text)
