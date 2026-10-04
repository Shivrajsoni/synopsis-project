"""Tests for Query Routing and Complexity Classifier."""
from src.router import classify_query


def test_classify_factoid_query():
    query = "What is the highest package in UIET placements?"
    route = classify_query(query)
    assert route.complexity == "factoid"
    assert route.top_k <= 3
    assert route.max_tokens <= 300

def test_classify_synthesis_query():
    query = "Compare UIET CSE placements versus IT department across last three years."
    route = classify_query(query)
    assert route.complexity == "synthesis"
    assert route.top_k >= 4
    assert route.max_tokens >= 500

def test_classify_balanced_query():
    query = "What is the fee for B.E. at UIET?"
    route = classify_query(query)
    assert route.complexity == "balanced"
    assert route.top_k == 3
    assert route.max_tokens == 350
