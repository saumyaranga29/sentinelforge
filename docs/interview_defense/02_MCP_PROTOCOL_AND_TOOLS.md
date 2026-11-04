# 02. Model Context Protocol (MCP) Server, Tools & Live Technical Defense

## 1. Protocol Architecture & Key Decisions

### ADR-02.1: Official FastMCP Protocol vs Direct Ad-Hoc Endpoints
* **Decision**: Implement the official Model Context Protocol using `mcp.server.fastmcp.FastMCP` and a dual `MCPDispatcher`.
* **Why**: The rubric specifically states:
  > *"The web application and coding agent must use MCP for the core tool workflow. Directly bypassing MCP for core operations will materially reduce the score."*
* Every core action (Ingest, Retrieve, Inspect, Patch, Execute) is encapsulated in an MCP Tool schema with typed Pydantic parameter definitions. The web API and Agent Orchestrator route actions through `mcp_dispatcher.call_tool()`, preserving 100% protocol fidelity.

### ADR-02.2: Tool Portfolio (7 Typed Tools - Exceeding Requirements for Bonus Points)
1. `ingest_content`: Content parsing, deduplication hashing, and vector indexing.
2. `retrieve_context`: Semantic search with exact citations and prompt-injection defense.
3. `inspect_repository`: Path-contained tree traversal and file reading.
4. `propose_patch`: Unified diff formulation (`diff -u`) with `PENDING_APPROVAL` staging.
5. `execute_in_sandbox`: Isolated subprocess execution with time, memory, and output guards.
6. `system_status` *(Bonus Tool)*: Platform operational telemetry, memory stats, and audit records.
7. `delete_indexed_content` *(Bonus Tool)*: Document removal from vector storage and hash registry.

### ADR-02.3: MCP Resources and Prompts
* **Resources**:
  - `repo://workspace/active_patch`: Exposes the currently staged unified diff awaiting human review.
  - `rag://index/stats`: Exposes real-time chunk metrics and indexed file counts.
* **Reusable Prompts**:
  - `task_planner`: Guides task decomposition, risk analysis, and retrieval strategy.
  - `code_review`: Evaluates proposed diffs for security, regressions, and test validity.

---

## 2. Senior Technical Interview & Defense Questions

### Question 1: "Why is protocol purity important, and how do you ensure the agent doesn't bypass MCP?"
**Candidate Answer**:
> "Protocol purity ensures interoperability and observability. If an agent directly invokes internal Python methods, external observability tools, protocol proxies, and multi-agent harnesses cannot inspect or intercept the tool calls. In SentinelForge, the `AgentOrchestrator` communicates exclusively through `mcp_dispatcher.call_tool()`. Every call is logged, validated against the tool's typed schema, and recorded in the audit trail."

### Question 2: "How do you handle schema validation and actionable errors across tools?"
**Candidate Answer**:
> "Each MCP tool has an associated Pydantic input model (`IngestContentInput`, `RetrieveContextInput`, `ProposePatchInput`, etc.). Before execution, arguments undergo strict validation. If a parameter violates constraints (e.g., `top_k > 20` or invalid file paths), the tool does not fail silently; it returns an actionable error message explaining the violated invariant and how to correct the input."

### Question 3: "What prevents an agent from executing infinite loops or hanging inside an MCP tool?"
**Candidate Answer**:
> "Every tool invocation is bounded:
> 1. In `execute_in_sandbox`, timeout defaults to 10 seconds (enforced via `subprocess.run(timeout=...)`). If exceeded, `TimeoutExpired` triggers process termination and returns `timed_out: true, exit_code: -9`.
> 2. File and directory traversal tools are bounded by `max_depth` (default 3) to prevent recursive directory loops.
> 3. Stream outputs are capped at 50KB to stop memory exhaustion."

---

## 3. Live Defense / Live Modification Scenarios

### Scenario A: "Add an 8th MCP tool during our live session."
* **File to Open**: [`sentinelforge/mcp/tools.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/mcp/tools.py) and [`sentinelforge/mcp/server.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/mcp/server.py)
* **Live Step-by-Step**:
  1. Define Pydantic model:
     ```python
     class LintCodeInput(BaseModel):
         file_path: str = Field(description="File to check for syntax and style")
     ```
  2. Implement handler `tool_lint_code(file_path: str) -> Dict[str, Any]` using `py_compile`.
  3. Register with `@mcp_app.tool()` in `server.py` and add to `MCPDispatcher.TOOLS`.
  4. Write a 3-line test in `tests/test_mcp_integration.py` proving discovery and execution.

### Scenario B: "How do you expose a new MCP Resource?"
* **File to Open**: [`sentinelforge/mcp/resources.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/mcp/resources.py)
* **Explanation**: Show how `@mcp_app.resource("repo://audit/recent")` maps a URI scheme to a read-only data provider, enabling external clients to inspect application state over standard protocol channels.
