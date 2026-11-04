from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sentinelforge.mcp.server import mcp_dispatcher

router = APIRouter(prefix="/api/mcp", tags=["Model Context Protocol"])


class InvokeToolRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the MCP tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary matching tool schema")


class RenderPromptRequest(BaseModel):
    prompt_name: str = Field(..., description="Name of the MCP prompt template")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables for prompt interpolation")


@router.get("/tools")
async def list_mcp_tools():
    """Returns schemas and documentation for all available MCP tools."""
    return {"tools": mcp_dispatcher.list_tools()}


@router.post("/tools/invoke")
async def invoke_mcp_tool(req: InvokeToolRequest):
    """Invokes a registered MCP tool via the standard dispatcher."""
    try:
        result = mcp_dispatcher.call_tool(req.tool_name, req.arguments)
        return {"tool": req.tool_name, "success": True, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/resources")
async def read_mcp_resource(uri: str):
    """Reads a registered MCP resource by URI."""
    try:
        data = mcp_dispatcher.read_resource(uri)
        return {"uri": uri, "content": data}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/prompts")
async def render_mcp_prompt(req: RenderPromptRequest):
    """Renders a reusable MCP prompt template."""
    try:
        rendered = mcp_dispatcher.get_prompt(req.prompt_name, **req.variables)
        return {"prompt_name": req.prompt_name, "rendered": rendered}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

