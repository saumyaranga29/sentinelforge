def test_openapi_schema_generated(client):
    """Verifies generated OpenAPI schema meets machine-readable documentation requirement."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "paths" in schema
    assert "/api/rag/query" in schema["paths"]
    assert "/api/mcp/tools" in schema["paths"]
    assert "/api/agent/run" in schema["paths"]


def test_health_endpoint(client):
    """Verifies health check endpoint returns 200 with operational metadata."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "SentinelForge"
    assert "is_local_processing" in data


def test_audit_logs_endpoint(client):
    """Verifies audit telemetry endpoint returns structured logs."""
    res = client.get("/api/audit/logs?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert isinstance(data["events"], list)


def test_mcp_tools_endpoint(client):
    """Verifies MCP tools listing endpoint."""
    res = client.get("/api/mcp/tools")
    assert res.status_code == 200
    data = res.json()
    assert "tools" in data
    assert len(data["tools"]) >= 5


def test_rag_query_endpoint(client):
    """Verifies RAG semantic search endpoint."""
    res = client.post("/api/rag/query", json={"query": "calculator arithmetic", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert "query" in data


def test_agent_run_endpoint(client):
    """Verifies Agent task execution endpoint."""
    res = client.post("/api/agent/run", json={"task": "Verify arithmetic operations"})
    assert res.status_code == 200
    data = res.json()
    assert data["stage_reached"] == "Stage 7: Final Report"
    assert data["status"] == "PENDING_APPROVAL"
    assert data["sandbox_executed"] is True

