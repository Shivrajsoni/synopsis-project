"""
Query Complexity Router for University RAG.
Classifies incoming student queries into:
1. FACTOID (direct lookups, single entities, links, phone numbers, codes)
2. SYNTHESIS (multi-aspect questions, subject schemes, research projects, procedures)
Directs retrieval top_k, generation token budget, and prompt instruction.
"""
import re
from dataclasses import dataclass


@dataclass
class RouteConfig:
    complexity: str        # 'factoid' or 'synthesis'
    top_k: int             # Number of context chunks needed
    max_tokens: int        # Generation budget for Ollama (num_predict)
    instruction: str       # Tailored brevity / structure guideline

# Regular expression cues for factoid vs synthesis
FACTOID_PATTERNS = [
    r"^who is\b",
    r"^what is the (official )?(site|portal|link|url|website|contact|email|phone)\b",
    r"\b(phone number|contact number|email id|portal link|official site)\b",
    r"\b(highest package|average package|cutoff|conversion formula)\b",
    r"^where is\b",
    r"^when was\b"
]

SYNTHESIS_PATTERNS = [
    r"\ball (ongoing )?research\b",
    r"\b(subjects|curriculum|scheme|syllabus)\b",
    r"\b(procedure|steps|how to apply|all hostels|residence halls)\b",
    r"\b(compare|comparison|difference between)\b",
    r"\blist all\b",
    r"\bprojects related to\b"
]

def classify_query(query: str) -> RouteConfig:
    """
    Classifies student query complexity to optimize retrieval depth and generation budget.
    Strategy 5 (Cascaded Routing).
    """
    q_lower = query.lower().strip()

    # Check synthesis indicators first
    for pat in SYNTHESIS_PATTERNS:
        if re.search(pat, q_lower):
            return RouteConfig(
                complexity="synthesis",
                top_k=4,
                max_tokens=650,
                instruction="Provide a structured, comprehensive answer with Markdown tables and clear headings where appropriate."
            )

    # Check factoid indicators
    for pat in FACTOID_PATTERNS:
        if re.search(pat, q_lower):
            return RouteConfig(
                complexity="factoid",
                top_k=2,
                max_tokens=160,
                instruction="Provide a direct, concise, and factual answer in 2-4 sentences without unnecessary preamble."
            )

    # Default fallback for balanced questions
    return RouteConfig(
        complexity="balanced",
        top_k=3,
        max_tokens=350,
        instruction="Provide a clear, accurate, and structured answer based strictly on verified facts."
    )
