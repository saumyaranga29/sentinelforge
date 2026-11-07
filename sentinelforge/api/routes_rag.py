from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from sentinelforge.config import settings
from sentinelforge.rag.vector_store import vector_store
from sentinelforge.sandbox.security import SandboxSecurityValidator

router = APIRouter(prefix="/api/rag", tags=["Local RAG"])


class QueryRequest(BaseModel):
    query: str = Field(..., description="Search query for semantic context retrieval")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context passages to return")


class QueryResponse(BaseModel):
    query: str
    count: int
    results: List[Dict[str, Any]]


class IngestTextRequest(BaseModel):
    filename: str = Field(..., description="Target filename including extension (e.g. docs.md, spec.txt)")
    content: str = Field(..., description="Text content to be stored and indexed")


@router.post("/query", response_model=QueryResponse)
async def query_rag(req: QueryRequest):
    """Performs semantic search over locally indexed documents and code with citations."""
    citations = vector_store.retrieve(query=req.query, top_k=req.top_k)
    return {
        "query": req.query,
        "count": len(citations),
        "results": [c.model_dump() for c in citations],
    }


@router.post("/ingest/text")
async def ingest_text(req: IngestTextRequest):
    """Ingests raw text under a virtual filename into local vector store."""
    target_path = (settings.workspace_root / req.filename).resolve()
    SandboxSecurityValidator.validate_path(target_path, settings.workspace_root)
    SandboxSecurityValidator.validate_file_extension(target_path)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(req.content, encoding="utf-8")

    result = vector_store.ingest_file(target_path)
    return result


@router.post("/ingest/upload")
async def ingest_upload(file: UploadFile = File(...)):
    """Uploads and indexes a document (PDF, Markdown, Python, JS, TS, JSON)."""
    file_path = Path(file.filename)
    SandboxSecurityValidator.validate_file_extension(file_path)

    target_path = (settings.workspace_root / file.filename).resolve()
    SandboxSecurityValidator.validate_path(target_path, settings.workspace_root)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    contents = await file.read()
    with open(target_path, "wb") as f:
        f.write(contents)

    result = vector_store.ingest_file(target_path)
    return result


@router.get("/stats")
async def get_rag_stats():
    """Returns local RAG index statistics, total chunks, and indexed files."""
    return vector_store.get_stats()


@router.delete("/content/{filename}")
async def delete_indexed_file(filename: str):
    """Deletes indexed chunks belonging to a specific source file."""
    deleted_count = vector_store.delete_by_source(filename)
    return {
        "status": "success",
        "file": filename,
        "deleted_chunks": deleted_count,
    }

