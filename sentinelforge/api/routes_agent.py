from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sentinelforge.agent.diff_engine import diff_engine
from sentinelforge.agent.orchestrator import AgentOrchestrator, AgentExecutionReport

router = APIRouter(prefix="/api/agent", tags=["Code-Generation Agent"])

orchestrator = AgentOrchestrator()


class AgentRunRequest(BaseModel):
    task: str = Field(..., description="Natural language description of coding change or bug fix")
    target_file: Optional[str] = Field(default=None, description="Optional target file to modify")
    code_override: Optional[str] = Field(default=None, description="Optional explicit code modification for testing")


class PatchApprovalRequest(BaseModel):
    patch_id: str = Field(..., description="ID of the patch proposal to approve or reject")
    approved: bool = Field(..., description="True to apply unified diff, False to reject")


@router.post("/run", response_model=AgentExecutionReport)
async def run_agent(req: AgentRunRequest):
    """
    Executes the 7-stage cognitive loop:
    Task Analysis -> Plan -> Retrieval -> Patch Proposal -> Sandbox Execution -> Self-Critique -> Final Report.
    """
    try:
        report = orchestrator.run(
            task=req.task,
            target_file=req.target_file,
            code_override=req.code_override,
        )
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failure: {str(exc)}")


@router.get("/patch/active")
async def get_active_patch():
    """Inspects the currently staged unified diff proposal."""
    patch = diff_engine.active_patch
    if not patch:
        return {"status": "none", "message": "No active patch staged."}
    return patch.model_dump()


@router.post("/patch/approve")
async def approve_patch(req: PatchApprovalRequest):
    """
    Explicit human-in-the-loop approval gate.
    No generated code is applied to the repository without explicit approval.
    """
    try:
        applied = diff_engine.apply_patch(patch_id=req.patch_id, approved=req.approved)
        return {
            "patch_id": req.patch_id,
            "status": "APPLIED" if applied else "REJECTED",
            "message": "Patch applied successfully to workspace." if applied else "Patch rejected by user.",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

