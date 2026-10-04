# Quickstart & Execution Guide: Panjab University RAG Assistant

This guide provides step-by-step instructions to set up, build, test, and run all components of the Panjab University & UIET RAG Assistant.

---

## 1. Environment Setup

### Prerequisites
- **Python**: Version `3.10` or `3.11` (Python 3.11 recommended).
- **Git**: Installed and configured.
- **Ollama (Optional for local LLM)**: Download from [ollama.com](https://ollama.com).

### Step 1: Create and Activate Virtual Environment
```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
# Install core runtime dependencies
pip install -r requirements.txt

# Install development & test dependencies
pip install -r requirements-dev.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure API keys if using cloud models (Google Gemini or Groq Cloud). If using Local Ollama or Offline mode, no API keys are required.

---

## 2. Knowledge Base & Vector Store Operations

The repository includes pre-processed chunks in `data/chunks/rag_chunks.jsonl`. You can index them into ChromaDB immediately.

### Index Chunks into ChromaDB
```bash
python -m src.vector_store
```
*Output*: `✓ Successfully indexed 660 vectors into 'panjab_university_rag'.`

### (Optional) Run Crawlers & Harvesters
To fetch live data from university portals:
```bash
# 1. Harvest expanded UIET pages & official handbooks
python src/deep_harvester.py

# 2. Extract full faculty profiles & fee schedules
python src/extract_full_faculty_and_institutes.py

# 3. Recursive multi-perspective deep crawler
python src/deep_crawler.py

# 4. Rebuild chunks and re-index vector store
python src/rebuild_all_chunks.py
```

### Preview Search Keywords Without Vector DB
To verify chunk keywords and breadcrumbs directly against `rag_chunks.jsonl`:
```bash
python src/search_preview.py "PULEET entrance test eligibility"
```

---

## 3. Running the Web Application & Server

The server provides a modern dark-mode single-page UI, Server-Sent Events (SSE) streaming, and REST APIs.

### Start the Server
```bash
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser and navigate to:
```text
http://localhost:8000
```

### API Endpoints
- `GET /` — Web interface
- `GET /api/stats` — Vector counts, document totals, cache telemetry
- `GET /api/health` — Backend and Ollama status
- `POST /api/chat` — Synchronous chat endpoint
- `POST /api/chat/stream` — SSE token streaming endpoint

---

## 4. Running CLI Query Sessions

The CLI engine (`src/rag_engine.py`) supports 4 switchable backends:

### Backend 1: Local Ollama (Default)
Ensure Ollama is running and has the model installed:
```bash
ollama run llama3.2:3b
```
Run query:
```bash
python -m src.rag_engine --backend ollama "What is the highest package in UIET placements?"
```

### Backend 2: Google Gemini Cloud
```bash
export GEMINI_API_KEY="your-gemini-key"
python -m src.rag_engine --backend gemini "What are the eligibility criteria for EWS freeship?"
```

### Backend 3: Groq Cloud (Ultra-Fast Llama 3.3 70B)
```bash
export GROQ_API_KEY="your-groq-key"
python -m src.rag_engine --backend groq "How is admission conducted via JAC Chandigarh?"
```

### Backend 4: Deterministic Grounded Offline Mode (No LLM required)
Works 100% offline with zero external API calls:
```bash
python -m src.rag_engine --backend offline "What is Shraman Foundation scholarship at UIET?"
```

### Interactive CLI Shell
```bash
python -m src.rag_engine
```
Type your queries at the prompt. Type `exit` or `quit` to exit.

---

## 5. Testing & Quality Verification

### Run Linter (Ruff)
```bash
ruff check src tests
```

### Run Unit & Integration Tests (Pytest)
```bash
pytest -v
```

### Run RAG Retrieval Evaluation Benchmark
Evaluates Hit Rate @ K and Mean Reciprocal Rank (MRR) across real student queries:
```bash
python -m src.evaluator 3
```
