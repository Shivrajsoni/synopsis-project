"""
University Chatbot RAG Query Engine.
Supports switchable LLM backends:
1. Google Gemini (via GEMINI_API_KEY)
2. Groq Cloud (via GROQ_API_KEY - Free high-speed Llama 3.3 70B)
3. Local Ollama (via http://localhost:11434 - 100% free offline on Mac)
4. Deterministic Grounded Extractor (Zero-dependency offline mode)
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path so script can run directly as `python src/...`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests

from src.retriever import HybridRetriever

SYSTEM_PROMPT = """You are the official Panjab University & UIET Academic, Admissions, and Campus Life AI Assistant.
Your task is to provide accurate, grounded answers to student queries based ONLY on the provided Context.

Strict Guidelines:
1. Grounding: Answer strictly using facts from the retrieved Context. Do not invent fees, dates, or eligibility.
2. Category Disambiguation: Carefully verify section headers and breadcrumbs. Do NOT confuse special category rules (such as Sports Quota, Foreign National, or PwD) with General Admission or General Hostel allotment. If a requirement (like ground attendance or sports trials) applies only to sports quota candidates, explicitly state that it applies to sports category only, not general students.
3. Faculty & People: When asked about a professor, faculty member, or university official, provide their full designation, department, administrative responsibilities (e.g. TPO in-charge or Warden), research areas, and contact information if available in context.
4. Citations: Always cite the source URL and official document name for key facts.
5. Honesty: If the retrieved context does not contain the answer, politely clarify what is known and provide the official university contact: 1800-180-2065.
"""

class RAGEngine:
    def __init__(self, backend: str = "auto", model_name: Optional[str] = None):
        self.retriever = HybridRetriever()
        self.backend = backend.lower()
        self.model_name = model_name
        self._detect_backend()

    def _detect_backend(self):
        """Detects available LLM backend."""
        if self.backend == "auto":
            if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                self.backend = "gemini"
            elif os.environ.get("GROQ_API_KEY"):
                self.backend = "groq"
            else:
                # Check if local Ollama is active
                try:
                    res = requests.get("http://localhost:11434/api/tags", timeout=1.0)
                    if res.status_code == 200:
                        self.backend = "ollama"
                    else:
                        self.backend = "offline"
                except Exception:
                    self.backend = "offline"

    def get_backend_info(self) -> Dict[str, str]:
        return {
            "backend": self.backend,
            "description": {
                "gemini": "Google Gemini API (gemini-1.5-flash / gemini-2.5-flash)",
                "groq": "Groq Cloud (llama-3.3-70b-versatile - Free high-speed tier)",
                "ollama": "Local Ollama (Apple Silicon Metal hardware accelerated)",
                "offline": "Deterministic Grounded Synthesizer (No API key required)"
            }.get(self.backend, "Custom Backend")
        }

    def build_prompt(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Formats context and user query into a structured LLM prompt."""
        context_str = ""
        for idx, chunk in enumerate(context_chunks, start=1):
            source = chunk["metadata"].get("source_url", "Official PU Portal")
            breadcrumb = chunk["metadata"].get("breadcrumb", "")
            tier = chunk["metadata"].get("authority_tier", "official_primary")
            context_str += f"\n--- [Document {idx}] Source: {source} (Tier: {tier}) | Path: {breadcrumb} ---\n"
            context_str += chunk["text"].strip() + "\n"

        prompt = f"""{SYSTEM_PROMPT}

CONTEXT INFORMATION:
{context_str}

STUDENT QUESTION:
{query}

ANSWER (with citations and clear markdown formatting):"""
        return prompt

    def query(self, question: str, top_k: int = 4) -> Dict[str, Any]:
        """Runs hybrid retrieval and generates an answer."""
        chunks = self.retriever.retrieve(query=question, top_k=top_k)
        prompt = self.build_prompt(question, chunks)

        citations = []
        for c in chunks:
            citations.append({
                "source_url": c["metadata"].get("source_url"),
                "category": c["metadata"].get("category"),
                "authority_tier": c["metadata"].get("authority_tier"),
                "breadcrumb": c["metadata"].get("breadcrumb"),
                "score": c.get("rrf_score")
            })

        answer = self._generate_answer(prompt, chunks)

        return {
            "question": question,
            "answer": answer,
            "backend_used": self.backend,
            "citations": citations,
            "context_chunks_count": len(chunks)
        }

    def _generate_answer(self, prompt: str, chunks: List[Dict[str, Any]]) -> str:
        """Dispatches generation to selected backend."""
        # 1. Google Gemini
        if self.backend == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if api_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    model_to_use = self.model_name or "gemini-1.5-flash"
                    model = genai.GenerativeModel(model_to_use)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        return response.text
                except Exception:
                    pass

        # 2. Groq Cloud (Free Llama 3.3 70B)
        elif self.backend == "groq":
            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key:
                try:
                    headers = {
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": self.model_name or "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2
                    }
                    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=20)
                    if res.status_code == 200:
                        return res.json()["choices"][0]["message"]["content"]
                except Exception:
                    pass

        # 3. Local Ollama (Local free Mac inference)
        elif self.backend == "ollama":
            try:
                payload = {
                    "model": self.model_name or "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False
                }
                res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=40)
                if res.status_code == 200:
                    return res.json().get("response", "")
            except Exception:
                pass

        # 4. Fallback: Deterministic Grounded Synthesis
        primary_chunk = chunks[0] if chunks else None
        if not primary_chunk:
            return "No verified information found in the Panjab University database for this query."

        top_sources = list({c["metadata"].get("source_url") for c in chunks if c["metadata"].get("source_url")})
        sources_md = "\n".join([f"- [{s}]({s})" for s in top_sources[:4]])

        return (
            f"### Verified Information from Official University Records:\n\n"
            f"{primary_chunk['text']}\n\n"
            f"**Official Sources & Citations:**\n{sources_md}\n\n"
            f"*For official confirmation, contact the Panjab University Enquiry Desk: 1800-180-2065.*"
        )

def main():
    parser = argparse.ArgumentParser(description="Panjab University RAG Chatbot")
    parser.add_argument("query", nargs="*", help="Question to ask the chatbot")
    parser.add_argument("--backend", default="auto", choices=["auto", "gemini", "groq", "ollama", "offline"], help="LLM backend to use")
    parser.add_argument("--model", default=None, help="Specific model name")
    args = parser.parse_args()

    engine = RAGEngine(backend=args.backend, model_name=args.model)
    info = engine.get_backend_info()

    if args.query:
        query_text = " ".join(args.query)
        res = engine.query(query_text)
        print(f"\n[Active Backend: {info['description']}]")
        print("\n" + res["answer"])
        print("\nTop Citations:")
        for idx, c in enumerate(res["citations"][:3], 1):
            print(f"  [{idx}] {c['source_url']} (Tier: {c['authority_tier']}, Path: {c['breadcrumb']})")
    else:
        print("\n" + "=" * 70)
        print("🏛️ PANJAB UNIVERSITY & UIET RAG ASSISTANT")
        print(f"Active Backend: {info['description']}")
        print("Type your questions below. Type 'exit' or 'quit' to terminate.")
        print("=" * 70 + "\n")
        while True:
            try:
                q = input("\nStudent Question > ").strip()
                if not q:
                    continue
                if q.lower() in ["exit", "quit", "q"]:
                    print("Exiting assistant.")
                    break
                res = engine.query(q)
                print("\n" + res["answer"])
                print("\nRetrieved Citations:")
                for idx, c in enumerate(res["citations"][:3], 1):
                    print(f"  [{idx}] {c['source_url']} (Tier: {c['authority_tier']}, Path: {c['breadcrumb']})")
            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    main()
