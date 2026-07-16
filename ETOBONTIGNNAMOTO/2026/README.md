# Local Research Engine

Local LangGraph pipeline for extracting, writing, and independently fact-checking three frontier-AI architecture papers with `llama3:latest` through Ollama.

Requires Python 3.10 or newer. Ollama is called through its local HTTP API; no Python Ollama client is required.

## Setup

Install dependencies and pre-stage text-extractable official PDFs:

```text
papers/deepseek-v3.pdf
papers/mamba-2.pdf
papers/bitnet-b1.58.pdf
```

Ollama must be running with `llama3:latest` installed.

## Run

```powershell
python research_engine.py --papers-dir papers
python research_engine.py --papers-dir papers --validate
python -m unittest -v
```

`--validate` first requires a clean approved run. It then launches a fresh graph with the deliberate Writer-prompt lie, verifies Critic rejection and `critic -> writer` routing, and expects termination at the three-attempt ceiling. Reports are saved under `artifacts/`.
