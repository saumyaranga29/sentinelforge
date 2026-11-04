# 01. System Architecture, Core Decisions & Live Technical Defense

## 1. Architectural Decisions (ADRs)

### ADR-01.1: Monolith vs Modular Micro-Architecture
* **Decision**: Single repository with strict modular boundaries (`sentinelforge/mcp`, `sentinelforge/rag`, `sentinelforge/sandbox`, `sentinelforge/agent`, `sentinelforge/api`).
* **Why**: The evaluation explicitly disqualifies single-file monoliths while requiring zero-cost reproducibility. Separate services would introduce networking overhead, port collision risks in containerized free tiers, and cross-process orchestration failure modes. Clean module boundaries preserve single-command testability.

### ADR-01.2: INR 0 Zero-Cost Deployment Architecture
* **Decision**: Single self-contained Docker container deployed to **Hugging Face Spaces (Docker Space)** or **Render Free**.
* **Why**:
  - Render free tier provides 512MB RAM and sleeps on idle, taking up to 60s for cold start.
  - Hugging Face Spaces provides **16GB RAM + 2 vCPU completely free**, zero card required, persistent public HTTPS URL, and does not sleep mid-evaluation.
  - Pluggable inference model: local lightweight quant / mock for offline evaluation + optional Groq free tier (30 RPM, no billing required).
* **Evaluator Friction Zero Policy**: No user accounts, evaluator API keys, or payment methods required. Tested to open cleanly in an incognito browser.

### ADR-01.3: Data Bootstrapping Without Persistent Disk
* **Decision**: Ephemeral filesystem resilience via `bootstrap_sample_data()` lifespan handler.
* **Why**: Cloud free tiers offer ephemeral storage. On container start, SentinelForge automatically initializes the sample repository (`calculator.py`, `test_calculator.py`) and indexes specification documents into the vector store. Evaluators never face an empty or broken platform.

---

## 2. Senior Technical Interview & Defense Questions

### Question 1: "Why did you choose FastMCP over custom REST/gRPC or LangChain tools?"
**Candidate Answer**:
> "FastMCP is the official open standard protocol designed specifically for agent-tool communication. By implementing MCP natively, SentinelForge is not tied to any proprietary agent framework or SDK. An external client like Claude Desktop or MCP Inspector can discover and invoke our tools immediately via SSE or Stdio. Furthermore, custom REST lacks standard schema reflection, resource URI subscriptions (`repo://workspace/active_patch`), and reusable prompt negotiation. LangChain or LlamaIndex would have added heavy transitive dependencies, making zero-cost containerization difficult."

### Question 2: "How do you handle container cold starts and memory constraints on free-tier cloud hosts?"
**Candidate Answer**:
> "Free hosting platforms typically cap memory at 512MB (Render) or 16GB (HF Spaces). If an application attempts to load a 7B parameter LLM into RAM, it OOM-kills immediately. SentinelForge solves this through three design choices:
> 1. Local RAG uses `fastembed` with ONNX CPU runtime (`bge-small-en-v1.5`), consuming only ~100MB RAM and running inference in under 40ms on pure CPU.
> 2. Vector indexing uses ChromaDB in embedded local mode without external server processes.
> 3. The LLM inference layer is pluggable: it uses lightweight CPU inference, local Ollama when run locally, or zero-cost cloud inference without evaluator API keys.
> 4. Application startup is non-blocking with an asynchronous lifespan handler."

### Question 3: "If an evaluator tests the deployed URL in an incognito window, what prevents state corruption across concurrent evaluations?"
**Candidate Answer**:
> "Every API request generates a unique `X-Request-ID` attached to a `ContextVar`. When the agent executes test runs inside the sandbox, it creates an isolated scratch workspace (`tempfile.TemporaryDirectory`) cloned from the active repository. The active codebase is never mutated until explicit human approval (`/api/agent/patch/approve`). As a result, parallel evaluation queries cannot corrupt each other or leave the repository in a broken state."

---

## 3. Live Defense / Live Modification Scenarios

### Scenario A: "Show me how you would add a new configuration setting and hot-reload it."
* **File to Open**: [`sentinelforge/config.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/config.py)
* **Explanation**: Explain Pydantic `BaseSettings` with environment variable overrides. Show how `Field(default_factory=...)` reads dynamically from `os.getenv` allowing zero-downtime configuration changes in Docker.

### Scenario B: "How do you prove that no secrets are leaking in logs?"
* **File to Open**: [`sentinelforge/utils/logging.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/utils/logging.py) and [`sentinelforge/sandbox/runner.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/runner.py)
* **Explanation**: Walk through `_get_scrubbed_env()`. Show how `os.environ` is scrubbed down to a whitelist of safe system variables, stripping any `*_API_KEY`, `TOKEN`, or cloud credentials before any command is executed.
