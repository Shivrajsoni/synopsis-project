# Contributing to Panjab University RAG Assistant

Thank you for your interest in contributing to the Panjab University RAG Assistant! We welcome community contributions, bug reports, and enhancements.

---

## Code of Conduct

Please be respectful, collaborative, and considerate when interacting with fellow contributors and maintainers.

---

## Development Setup

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/your-username/synopsis.git
cd synopsis

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install runtime & development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add any API keys if testing cloud backends (`GEMINI_API_KEY` or `GROQ_API_KEY`).

### 3. Build Vector Store Index
Index the chunk dataset into ChromaDB:
```bash
python -m src.vector_store
```

---

## Running Quality Checks & Tests

Before submitting a Pull Request, ensure that all linting checks and automated tests pass:

### Linting & Formatting
```bash
# Check code style with Ruff
ruff check src tests

# Check formatting (optional check)
ruff format --check src tests
```

### Running Test Suite
```bash
# Run automated pytest suite
pytest -v

# Run RAG evaluation benchmark
python -m src.evaluator
```

---

## Making Changes & Submitting Pull Requests

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Commit Your Changes**:
   Write concise, descriptive commit messages adhering to conventional commit style:
   ```bash
   git commit -m "feat(retriever): optimize token scoring bonus"
   ```
3. **Verify Zero Regressions**:
   Ensure all tests pass and no linter warnings remain.
4. **Push Branch & Open a Pull Request**:
   Push to your fork and submit a PR against `main`. Provide a clear description of the problem solved.
