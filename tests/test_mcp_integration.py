from pathlib import Path
from sentinelforge.mcp.server import mcp_dispatcher


def test_mcp_tools_discovery():
    """Verifies that an MCP client can discover all registered tools."""
    tools = mcp_dispatcher.list_tools()
    assert len(tools) >= 6  # Exceeds 5-tool requirement
    tool_names = [t["name"] for t in tools]
    assert "ingest_content" in tool_names
    assert "retrieve_context" in tool_names
    assert "inspect_repository" in tool_names
    assert "propose_patch" in tool_names
    assert "execute_in_sandbox" in tool_names
    assert "system_status" in tool_names


def test_mcp_inspect_repository_tool(temp_workspace):
    """Verifies inspect_repository tool returns directory contents with file metadata."""
    res = mcp_dispatcher.call_tool("inspect_repository", {"relative_path": ""})
    assert res["type"] == "directory"
    paths = [item["path"] for item in res["tree"]]
    assert "calculator.py" in paths


def test_mcp_propose_patch_tool(temp_workspace):
    """Verifies propose_patch tool creates a unified diff and stages it as PENDING_APPROVAL."""
    orig = "def add(a, b):\n    return a + b\n"
    mod = "def add(a, b):\n    \"\"\"Sum numbers.\"\"\"\n    return a + b\n"

    res = mcp_dispatcher.call_tool(
        "propose_patch",
        {
            "target_file": "calculator.py",
            "original_content": orig,
            "modified_content": mod,
            "rationale": "Add docstring to add function",
        },
    )

    assert res["status"] == "staged_pending_approval"
    assert "--- a/calculator.py" in res["unified_diff"]
    assert "+    \"\"\"Sum numbers.\"\"\"" in res["unified_diff"]


def test_mcp_execute_sandbox_tool(temp_workspace):
    """Verifies execute_in_sandbox tool runs Python test code within sandbox."""
    res = mcp_dispatcher.call_tool(
        "execute_in_sandbox",
        {
            "command": "python",
            "args": ["-c", "print('MCP_SANDBOX_SUCCESS')"],
            "timeout_seconds": 5,
        },
    )
    assert res["exit_code"] == 0
    assert "MCP_SANDBOX_SUCCESS" in res["stdout"]


def test_mcp_system_status_tool():
    """Verifies system_status tool returns operational health and configuration."""
    res = mcp_dispatcher.call_tool("system_status", {})
    assert res["status"] == "healthy"
    assert "rag" in res
    assert "app_name" in res


def test_mcp_resource_reading():
    """Verifies MCP client can read registered resources."""
    stats = mcp_dispatcher.read_resource("rag://index/stats")
    assert "total_chunks" in stats

    patch_text = mcp_dispatcher.read_resource("repo://workspace/active_patch")
    assert isinstance(patch_text, str)


def test_mcp_prompt_rendering():
    """Verifies MCP client can fetch and render reusable prompt templates."""
    rendered = mcp_dispatcher.get_prompt(
        "task_planner",
        task_description="Add zero check to divide",
        repo_summary="calculator.py, test_calculator.py",
    )
    assert "Add zero check to divide" in rendered
    assert "SentinelForge Agent" in rendered

