from typing import Any, Dict
from sentinelforge.agent.diff_engine import diff_engine
from sentinelforge.rag.vector_store import vector_store


def get_active_patch_resource() -> str:
    """Returns the unified diff and metadata of the currently staged patch."""
    patch = diff_engine.active_patch
    if not patch:
        return "No patch currently staged for review."

    return (
        f"--- ACTIVE STAGED PATCH ---\n"
        f"Patch ID: {patch.patch_id}\n"
        f"Target File: {patch.target_file}\n"
        f"Status: {patch.status}\n"
        f"Rationale: {patch.rationale}\n\n"
        f"Unified Diff:\n{patch.unified_diff}\n"
    )


def get_rag_stats_resource() -> Dict[str, Any]:
    """Returns real-time RAG index status and chunk counts."""
    return vector_store.get_stats()

