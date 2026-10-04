"""
RAG Evaluation Harness & Benchmark Suite for Panjab University Assistant.
Evaluates Hybrid Retrieval across real test queries, calculating HitRate@K and MRR (Mean Reciprocal Rank).
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path so script can run directly as `python src/...`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import HybridRetriever

# Standard Benchmark Dataset based on Panjab University & UIET Admissions
EVALUATION_BENCHMARK = [
    {
        "query": "What is the highest and average package in UIET placements?",
        "expected_keywords": ["45 LPA", "8.72 LPA", "placements"],
        "category": "UIET general"
    },
    {
        "query": "How many student residence halls and hostels are in Panjab University?",
        "expected_keywords": ["21 Residence Halls", "7600 students", "boys", "girls"],
        "category": "UIET general"
    },
    {
        "query": "What are the eligibility and rules for EWS freeship tuition fee concession?",
        "expected_keywords": ["freeship", "2.5 lac", "tuition fee concession", "60%"],
        "category": "Scholarship"
    },
    {
        "query": "Which entrance test is required for B.E. lateral entry at Panjab University?",
        "expected_keywords": ["PULEET", "Diploma in Engineering", "B.E."],
        "category": "Admission"
    },
    {
        "query": "What are the dates and eligibility for PUTHAT hotel management entrance test?",
        "expected_keywords": ["PUTHAT", "Bachelor of Hotel Management", "10+2"],
        "category": "Admission"
    },
    {
        "query": "How is admission conducted for B.E. programs in UIET through JAC Chandigarh?",
        "expected_keywords": ["JAC", "JEE Main", "counselling", "spot round"],
        "category": "Admission"
    },
    {
        "query": "What is the fee structure for M.Tech programs at UIET Chandigarh?",
        "expected_keywords": ["M.Tech", "fees", "1.23 L"],
        "category": "Secondary"
    }
]

def run_evaluation(top_k: int = 3):
    retriever = HybridRetriever()
    print("\n" + "=" * 70)
    print(f"RUNNING RAG EVALUATION BENCHMARK (Top-{top_k} Retrieval)")
    print("=" * 70)

    total_queries = len(EVALUATION_BENCHMARK)
    hits = 0
    reciprocal_ranks = []

    for idx, test in enumerate(EVALUATION_BENCHMARK, start=1):
        q = test["query"]
        expected = test["expected_keywords"]
        results = retriever.retrieve(query=q, top_k=top_k)

        # Check if any retrieved chunk contains the ground truth keywords
        hit_rank = None
        for rank, r in enumerate(results, start=1):
            text_lower = r["text"].lower()
            if any(k.lower() in text_lower for k in expected):
                hit_rank = rank
                break

        if hit_rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / hit_rank)
            status = f"✓ PASS (Rank {hit_rank})"
        else:
            reciprocal_ranks.append(0.0)
            status = "✗ FAIL"

        print(f"[{idx}/{total_queries}] Query: '{q}' -> {status}")

    hit_rate = (hits / total_queries) * 100
    mrr = sum(reciprocal_ranks) / total_queries

    print("\n" + "=" * 70)
    print("EVALUATION METRICS:")
    print(f"  • Hit Rate @ {top_k}: {hit_rate:.1f}% ({hits}/{total_queries} queries retrieved ground truth)")
    print(f"  • Mean Reciprocal Rank (MRR): {mrr:.3f}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    k_val = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    run_evaluation(top_k=k_val)
