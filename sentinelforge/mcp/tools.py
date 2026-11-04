import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sentinelforge.agent.diff_engine import diff_engine
from sentinelforge.config import settings
from sentinelforge.rag.vector_store import vector_store
from sentinelforge.sandbox.runner import SandboxRunner
from sentinelforge.sandbox.security import SandboxSecurityValidator
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.mcp.tools")

sandbox_runner = SandboxRunner()


# Typed Tool Input Models
class IngestContentInput(BaseModel):
    file_path: str = Field(description="Relative or absolute path to the document or code file to index")


class RetrieveContextInput(BaseModel):
    query: str = Field(description="Search query to retrieve semantic context from indexed documents")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of context chunks to return")


class InspectRepositoryInput(BaseModel):
    relative_path: str = Field(default="", description="Relative path in repository workspace to inspect")
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum directory traversal depth")


class ProposePatchInput(BaseModel):
    target_file: str = Field(description="Relative path of the target file to be modified")
    original_content: str = Field(description="Original file content before modification")
    modified_content: str = Field(description="New proposed content for the target file")
    rationale: str = Field(description="Clear explanation of the reasoning and impact of the patch")


class ExecuteSandboxInput(BaseModel):
    command: str = Field(description="Command to execute in sandbox (must be 'python', 'pytest', or 'node')")
    args: List[str] = Field(default_factory=list, description="List of arguments for the command")
    timeout_seconds: int = Field(default=10, ge=1, le=60, description="Execution timeout limit in seconds")
    language: str = Field(default="python", description="Language runner environment ('python' or 'javascript')")


class DeleteContentInput(BaseModel):
    file_path: str = Field(description="Filename of the indexed document to delete from vector storage")


# Tool Implementation Handlers
def tool_ingest_content(file_path: str) -> Dict[str, Any]:
    """Ingests, chunks, hashes, and indexes a file into the local vector store."""
    path = Path(file_path)
    if not path.is_absolute():
        path = (settings.workspace_root / path).resolve()

    return vector_store.ingest_file(path)


def tool_retrieve_context(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Retrieves relevant semantic context chunks with source citations and injection defense."""
    citations = vector_store.retrieve(query=query, top_k=top_k)
    return {
        "query": query,
        "count": len(citations),
        "results": [c.model_dump() for c in citations],
    }


def tool_inspect_repository(relative_path: str = "", max_depth: int = 3) -> Dict[str, Any]:
    """Safely inspects the repository directory tree and file list."""
    target_dir = settings.workspace_root / relative_path
    validated_path = SandboxSecurityValidator.validate_path(target_dir, settings.workspace_root)

    if not validated_path.exists():
        return {"error": f"Path '{relative_path}' does not exist in workspace."}

    if validated_path.is_file():
        SandboxSecurityValidator.validate_file_extension(validated_path)
        content = validated_path.read_text(encoding="utf-8", errors="replace")
        return {
            "type": "file",
            "path": relative_path,
            "size_bytes": len(content),
            "content": content,
        }

    tree: List[Dict[str, Any]] = []
    base_depth = len(validated_path.parts)

    for item in validated_path.glob("**/*"):
        cur_depth = len(item.parts) - base_depth
        if cur_depth > max_depth:
            continue
        rel = os.path.relpath(os.path.realpath(str(item)), os.path.realpath(str(settings.workspace_root)))
        tree.append({
            "path": str(rel).replace("\\", "/"),
            "is_dir": item.is_dir(),
            "size_bytes": item.stat().st_size if item.is_file() else 0,
        })

    return {
        "type": "directory",
        "root": relative_path or "/",
        "total_items": len(tree),
        "tree": tree,
    }


def tool_propose_patch(
    target_file: str,
    original_content: str,
    modified_content: str,
    rationale: str,
) -> Dict[str, Any]:
    """Generates a unified diff proposal and stages it for human review."""
    proposal = diff_engine.create_patch(
        target_file=target_file,
        original_content=original_content,
        modified_content=modified_content,
        rationale=rationale,
    )
    return {
        "status": "staged_pending_approval",
        "patch_id": proposal.patch_id,
        "target_file": proposal.target_file,
        "unified_diff": proposal.unified_diff,
        "rationale": proposal.rationale,
    }


def tool_execute_in_sandbox(
    command: str,
    args: Optional[List[str]] = None,
    timeout_seconds: int = 10,
    language: str = "python",
) -> Dict[str, Any]:
    """Executes a command inside the isolated sandbox environment."""
    result = sandbox_runner.execute(
        command=command,
        args=args or [],
        timeout_seconds=timeout_seconds,
    )
    return result.model_dump()


def tool_system_status() -> Dict[str, Any]:
    """Returns platform operational health, active model mode, and audit status (Bonus Tool)."""
    rag_stats = vector_store.get_stats()
    audit_events = audit_logger.get_recent_events(limit=10)
    active_patch = diff_engine.active_patch

    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "app_mode": settings.app_mode,
        "llm_provider": settings.llm_provider,
        "rag": rag_stats,
        "active_patch": active_patch.model_dump() if active_patch else None,
        "recent_audit_count": len(audit_events),
    }


def tool_delete_indexed_content(file_path: str) -> Dict[str, Any]:
    """Deletes indexed chunks from vector storage by filename (Bonus Tool)."""
    deleted_count = vector_store.delete_by_source(Path(file_path).name)
    return {
        "status": "success",
        "file": file_path,
        "deleted_chunks": deleted_count,
    }

