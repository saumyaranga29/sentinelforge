from typing import Any, Dict, List, Optional
from sentinelforge.mcp.tools import (
    tool_ingest_content,
    tool_retrieve_context,
    tool_inspect_repository,
    tool_propose_patch,
    tool_execute_in_sandbox,
    tool_system_status,
    tool_delete_indexed_content,
)
from sentinelforge.mcp.resources import get_active_patch_resource, get_rag_stats_resource
from sentinelforge.mcp.prompts import get_task_planner_prompt, get_code_review_prompt
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.mcp.server")

try:
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:
        from mcp.server.fastmcp import FastMCP

    mcp_app = FastMCP(
        name="SentinelForge-MCP",
        description="Official Model Context Protocol server for SentinelForge platform",
    )
    logger.info("Official MCP Server initialized successfully.")
except Exception as e:
    mcp_app = None
    logger.warning(f"Official MCP Server initialization notice: {e}. Using standard protocol dispatcher.")


if mcp_app is not None:
    @mcp_app.tool()
    def ingest_content(file_path: str) -> Dict[str, Any]:
        """Ingests, chunks, and indexes a file into local RAG vector store."""
        return tool_ingest_content(file_path)

    @mcp_app.tool()
    def retrieve_context(query: str, top_k: int = 5) -> Dict[str, Any]:
        """Retrieves cited context chunks with prompt-injection defense."""
        return tool_retrieve_context(query, top_k)

    @mcp_app.tool()
    def inspect_repository(relative_path: str = "", max_depth: int = 3) -> Dict[str, Any]:
        """Safely inspects the repository file tree and contents."""
        return tool_inspect_repository(relative_path, max_depth)

    @mcp_app.tool()
    def propose_patch(target_file: str, original_content: str, modified_content: str, rationale: str) -> Dict[str, Any]:
        """Generates a unified diff proposal and stages it for human review."""
        return tool_propose_patch(target_file, original_content, modified_content, rationale)

    @mcp_app.tool()
    def execute_in_sandbox(command: str, args: List[str] = [], timeout_seconds: int = 10, language: str = "python") -> Dict[str, Any]:
        """Executes a command inside the isolated sandbox environment."""
        return tool_execute_in_sandbox(command, args, timeout_seconds, language)

    @mcp_app.tool()
    def system_status() -> Dict[str, Any]:
        """Returns platform operational health, active model mode, and audit status."""
        return tool_system_status()

    @mcp_app.tool()
    def delete_indexed_content(file_path: str) -> Dict[str, Any]:
        """Deletes indexed chunks from vector storage by filename."""
        return tool_delete_indexed_content(file_path)

    @mcp_app.resource("repo://workspace/active_patch")
    def active_patch_resource() -> str:
        """Resource exposing the staged unified diff."""
        return get_active_patch_resource()

    @mcp_app.resource("rag://index/stats")
    def rag_stats_resource() -> str:
        """Resource exposing index chunk counts and stats."""
        import json
        return json.dumps(get_rag_stats_resource())

    @mcp_app.prompt("task_planner")
    def task_planner(task_description: str) -> str:
        """Prompt guiding task decomposition and planning."""
        return get_task_planner_prompt(task_description)

    @mcp_app.prompt("code_review")
    def code_review(target_file: str, unified_diff: str) -> str:
        """Prompt guiding code review of staged patches."""
        return get_code_review_prompt(target_file, unified_diff)


class MCPDispatcher:
    """
    Standard protocol dispatcher for direct execution, tool discovery, and REST API bridging.
    Ensures that whether accessed via FastMCP stdio/SSE or FastAPI REST, the tools run uniformly.
    """

    TOOLS = {
        "ingest_content": tool_ingest_content,
        "retrieve_context": tool_retrieve_context,
        "inspect_repository": tool_inspect_repository,
        "propose_patch": tool_propose_patch,
        "execute_in_sandbox": tool_execute_in_sandbox,
        "system_status": tool_system_status,
        "delete_indexed_content": tool_delete_indexed_content,
    }

    RESOURCES = {
        "repo://workspace/active_patch": get_active_patch_resource,
        "rag://index/stats": get_rag_stats_resource,
    }

    PROMPTS = {
        "task_planner": get_task_planner_prompt,
        "code_review": get_code_review_prompt,
    }

    @classmethod
    def list_tools(cls) -> List[Dict[str, Any]]:
        """Returns schema metadata for all registered MCP tools."""
        return [
            {
                "name": "ingest_content",
                "description": "Ingests, chunks, and indexes a file into local RAG vector store.",
                "parameters": {"file_path": "string"},
            },
            {
                "name": "retrieve_context",
                "description": "Retrieves cited context chunks with prompt-injection defense.",
                "parameters": {"query": "string", "top_k": "integer"},
            },
            {
                "name": "inspect_repository",
                "description": "Safely inspects the repository file tree and contents.",
                "parameters": {"relative_path": "string", "max_depth": "integer"},
            },
            {
                "name": "propose_patch",
                "description": "Generates a unified diff proposal and stages it for human review.",
                "parameters": {
                    "target_file": "string",
                    "original_content": "string",
                    "modified_content": "string",
                    "rationale": "string",
                },
            },
            {
                "name": "execute_in_sandbox",
                "description": "Executes a command inside the isolated sandbox environment.",
                "parameters": {
                    "command": "string",
                    "args": "list[string]",
                    "timeout_seconds": "integer",
                    "language": "string",
                },
            },
            {
                "name": "system_status",
                "description": "Returns platform operational health, active model mode, and audit status.",
                "parameters": {},
            },
            {
                "name": "delete_indexed_content",
                "description": "Deletes indexed chunks from vector storage by filename.",
                "parameters": {"file_path": "string"},
            },
        ]

    @classmethod
    def call_tool(cls, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches an MCP tool call by name with validated arguments."""
        if name not in cls.TOOLS:
            raise ValueError(f"Unknown MCP tool: '{name}'. Available: {list(cls.TOOLS.keys())}")
        handler = cls.TOOLS[name]
        return handler(**arguments)

    @classmethod
    def read_resource(cls, uri: str) -> Any:
        """Reads a registered MCP resource."""
        if uri not in cls.RESOURCES:
            raise ValueError(f"Resource URI '{uri}' not found.")
        return cls.RESOURCES[uri]()

    @classmethod
    def get_prompt(cls, name: str, **kwargs) -> str:
        """Fetches and renders a registered MCP prompt."""
        if name not in cls.PROMPTS:
            raise ValueError(f"Prompt '{name}' not found.")
        return cls.PROMPTS[name](**kwargs)


mcp_dispatcher = MCPDispatcher()

