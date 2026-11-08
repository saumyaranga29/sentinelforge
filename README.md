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

## 🌐 Live Application

| Resource | Link |
|---|---|
| Live Platform | https://sentinelforge-sn45.onrender.com |
| GitHub Repository | https://github.com/saumyaranga29/sentinelforge |
| Health Endpoint | https://sentinelforge-sn45.onrender.com/health |



The workflow is:

1. Analyze the requested development task.
2. Generate an implementation plan.
3. Retrieve relevant repository context.
4. Propose code modifications.
5. Generate a unified diff.
6. Execute permitted validation in the sandbox.
7. Perform self-critique.
8. Present the proposed changes for human review.
9. Apply changes only after explicit approval.

Every proposed patch enters a pending approval state.

The developer retains control over whether the changes are accepted or rejected.

---

### Seven-Stage Agent Workflow

The coding agent follows a structured execution lifecycle:

| Stage | Process |
|---|---|
| 1 | Task Analysis |
| 2 | Plan Generation |
| 3 | Context Retrieval |
| 4 | Patch Proposal |
| 5 | Sandbox Execution |
| 6 | Self-Critique |
| 7 | Final Report |

This workflow improves traceability and separates code generation from code authorization.

---

## 🔐 Security Engineering

Security is a foundational part of SentinelForge rather than an additional feature.

| Threat | Implemented Defense |
|---|---|
| Directory traversal | Canonical path validation |
| Symlink escape | Workspace containment checks |
| Unauthorized commands | Strict command allowlist |
| Shell injection | Input validation and command restrictions |
| Malicious file types | Extension validation |
| Infinite execution | Subprocess timeouts |
| Excessive output | Output size limits |
| Environment leakage | Environment scrubbing |
| Prompt injection | Injection detection and context isolation |
| Unauthorized code modification | Human approval gate |


---


## ⚙️ Technology Stack

| Layer | Technology |
|---|---|
| Programming Language | Python 3.11+ |
| Backend Framework | FastAPI |
| API Server | Uvicorn |
| Agent Protocol | Model Context Protocol (MCP) |
| MCP Framework | FastMCP |
| Embedding Model | BAAI/bge-small-en-v1.5 |
| Embedding Runtime | FastEmbed / ONNX |
| Vector Database | ChromaDB |
| Document Processing | PyPDF |
| Data Validation | Pydantic |
| Code Execution | Python Subprocess Sandbox |
| Testing | Pytest |
| Containerization | Docker |
| Deployment | Render |

---

## 👩‍💻 Author

**Saumya Ranga**

B.Tech – Computer Science Engineering (Artificial Intelligence & Machine Learning)

[GitHub](https://github.com/saumyaranga29)

---
