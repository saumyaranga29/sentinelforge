# SentinelForge



[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/MCP-Official%20FastMCP%201.3+-purple.svg)](https://modelcontextprotocol.io)

**SentinelForge** is a privacy-first AI developer platform integrating an official **Model Context Protocol (MCP)** server, a local **Retrieval-Augmented Generation (RAG)** pipeline, a **sandboxed code-generation agent**, and a high-performance **REST API** with secure zero-cost deployment.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Client & Evaluation Interface                       │
│      (FastAPI OpenAPI /docs, ReDoc, External MCP Clients / Inspector)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SentinelForge MCP Server (FastMCP)                   │
│                                                                         │
│  Tools (7):                                                             │
│   • ingest_content          • retrieve_context    • inspect_repository  │
│   • propose_patch           • execute_in_sandbox  • system_status       │
│   • delete_indexed_content                                              │
│                                                                         │
│  Resources:                             Prompts:                        │
│   • repo://workspace/active_patch         • task_planner                 │
│   • rag://index/stats                    • code_review                  │
└────────────┬───────────────────────┬─────────────────────────┬──────────┘
             │                       │                         │
             ▼                       ▼                         ▼
┌─────────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│   Local RAG Pipeline    │ │  Code-Gen Agent   │ │   Isolated Sandbox    │
│                         │ │  7-Stage Loop:    │ │                       │
│ • FastEmbed (ONNX CPU)  │ │  1. Task Analysis │ │ • Workspace Jail      │
│ • ChromaDB / In-Memory  │ │  2. Plan Gen      │ │ • Path Traversal Blk  │
│ • SHA-256 Deduplication │ │  3. Retrieval     │ │ • Command Allowlist   │
│ • Citations (line/page) │ │  4. Patch Propose │ │ • Memory/Timeout Caps │
│ • Injection Guard       │ │  5. Sandbox Exec  │ │ • Truncation Guard    │
│   (UUID Delimiters)     │ │  6. Self-Critique │ │ • Zero Silent Mutation│
│                         │ │  7. Final Report  │ │   (Human Approval)    │
└─────────────────────────┘ └───────────────────┘ └───────────────────────┘
```

---

## 2. Mandatory Technical Highlights

### 2.1 Model Context Protocol (MCP) Server
* **Official SDK**: Built using the official Anthropic/Linux Foundation `mcp` SDK (`FastMCP`).
* **Tool Coverage**: Implements **7 typed tools** (exceeding the 5-tool requirement for +2 bonus points): `ingest_content`, `retrieve_context`, `inspect_repository`, `propose_patch`, `execute_in_sandbox`, `system_status`, `delete_indexed_content`.
* **Protocol Purity**: Coding agent and API core operations strictly route through MCP tools. Direct bypasses are prohibited.
* **Resources & Prompts**: Exposes live unified diff status (`repo://workspace/active_patch`), index telemetry (`rag://index/stats`), and reusable prompts (`task_planner`, `code_review`).

### 2.2 Privacy-First Local RAG Pipeline
* **Zero Cloud Cost / Offline Mode**: Uses `fastembed` with `BAAI/bge-small-en-v1.5` running on CPU via ONNX (~40ms per query, ~100MB RAM). Zero paid APIs, purchased credits, or external network calls required.
* **Multi-Format Ingestion**: Supports `.pdf`, `.md`, `.py`, `.js`, `.ts`, `.json`, and `.txt` files.
* **Exact Citations**: Returns citations preserving source filename, page number (for PDFs), section headers (for Markdown), and exact line ranges (for code).
* **Deduplication & Incremental Updates**: Tracks SHA-256 content hashes to skip duplicate files and supports individual document deletion.
* **Prompt Injection Defense**: Evaluates all untrusted document chunks with `PromptInjectionGuard`, detecting direct instruction overrides, jailbreaks (`DAN mode`), and special tokens (`<|im_start|>`). Chunks are encapsulated in cryptographic UUID boundary containers (`<untrusted_context_chunk id="...">`).

### 2.3 Sandboxed Code-Generation Agent
* **Deterministic 7-Stage Loop**:
  $$\text{Task Analysis} \longrightarrow \text{Plan} \longrightarrow \text{Retrieval} \longrightarrow \text{Patch Proposal} \longrightarrow \text{Sandbox Exec} \longrightarrow \text{Self-Critique} \longrightarrow \text{Final Report}$$
* **Unified Diff Format**: Code changes are formulated strictly as `diff -u` patches.
* **Zero Silent Mutation**: All proposed patches enter `PENDING_APPROVAL` status. Files in the repository are **never** silently modified without explicit human sign-off.
* **Sandbox Security & Resource Jails**:
  - Resolves canonical paths (`Path.resolve().is_relative_to(workspace_root)`) to stop directory traversal attacks (`../../etc/passwd`).
  - Detects and blocks symlinks pointing outside the workspace.
  - Enforces execution timeouts (10s default), memory caps, process limits, and 50KB output stream truncation.
  - Command allowlist (`python`, `pytest`).
  - Python test runner (`unittest`/`pytest`) in an ephemeral sandbox.

---

## 3. Quick Start (Reproducibility)

### 3.1 Local Setup

```bash
# Clone repository
git clone https://github.com/your-username/SentinelForge.git
cd SentinelForge

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate

# Install deterministic dependencies
pip install -r requirements.txt

# Run all automated tests (35 automated tests including security suite)
make test

# Run the in-repo retrieval evaluation benchmark (8 golden queries)
make eval

# Start the REST API server
make run
```
API Documentation will be live at: `http://localhost:8000/docs`

### 3.2 Docker Setup (Zero-Cost Deployment)

```bash
# Build and run self-contained Docker container
make docker-build
make docker-run
```

---

## 4. Zero-Cost & Deployment Compliance

* **Cost**: **INR 0**.
* **Model Inference**: Pluggable provider supports local Ollama / GGUF or free cloud tiers (Groq free tier) with zero credit card required.
* **Hosting Target**: Hugging Face Spaces Docker container (16GB RAM, 2 vCPU, permanent free tier) or Render Free.
* **Incognito Browser Verified**: Does not require evaluator account or API keys. Safely bootstraps sample repository (`sample_repo/calculator.py` and `docs/spec.md`) on startup.

