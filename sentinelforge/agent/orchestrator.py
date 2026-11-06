import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sentinelforge.agent.diff_engine import PatchProposal
from sentinelforge.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    STAGE_ANALYSIS_PROMPT,
    STAGE_PLAN_PROMPT,
    STAGE_CRITIQUE_PROMPT,
)
from sentinelforge.agent.providers import BaseLLMProvider, get_llm_provider
from sentinelforge.config import settings
from sentinelforge.mcp.server import mcp_dispatcher
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.agent.orchestrator")


class AgentExecutionReport(BaseModel):
    """Complete structured report of the 7-stage agent execution loop."""

    task: str
    stage_reached: str
    plan: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    patch_id: Optional[str] = None
    target_file: Optional[str] = None
    unified_diff: Optional[str] = None
    rationale: Optional[str] = None
    sandbox_executed: bool = False
    sandbox_success: bool = False
    test_summary: Optional[Dict[str, Any]] = None
    self_critique: str = ""
    risk_notes: List[str] = Field(default_factory=list)
    status: str = "PENDING_APPROVAL"


class AgentOrchestrator:
    """
    Executes the 7-stage cognitive loop:
    Task Analysis -> Plan -> Retrieval -> Patch Proposal -> Sandbox Execution -> Self-Critique -> Final Report.
    Strictly interacts via MCP tools and enforces safe sandboxed testing without modifying live files.
    """

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        self.workspace_root = (workspace_root or settings.workspace_root).resolve()
        self.llm = llm_provider or get_llm_provider()

    def run(
        self,
        task: str,
        target_file: Optional[str] = None,
        code_override: Optional[str] = None,
    ) -> AgentExecutionReport:
        """Runs the complete 7-stage execution loop."""
        logger.info(f"Initiating agent execution loop for task: {task[:80]}")

        # --- Stage 1: Task Analysis ---
        repo_inspection = mcp_dispatcher.call_tool("inspect_repository", {"relative_path": ""})
        analysis_prompt = STAGE_ANALYSIS_PROMPT.format(
            task=task,
            repo_files=str(repo_inspection.get("tree", [])[:10]),
        )
        task_analysis = self.llm.generate(AGENT_SYSTEM_PROMPT, analysis_prompt)

        # --- Stage 2: Plan Generation ---
        plan_prompt = STAGE_PLAN_PROMPT.format(task=task, analysis=task_analysis)
        plan = self.llm.generate(AGENT_SYSTEM_PROMPT, plan_prompt)

        # --- Stage 3: Context Retrieval via MCP ---
        retrieval_res = mcp_dispatcher.call_tool(
            "retrieve_context",
            {"query": task, "top_k": 3},
        )
        citations = retrieval_res.get("results", [])

        # --- Stage 4: Patch Proposal via MCP ---
        # Identify target file if not provided
        resolved_target = target_file
        if not resolved_target:
            import re
            py_match = re.search(r'\b([a-zA-Z0-9_\-]+\.py)\b', task)
            if py_match:
                resolved_target = py_match.group(1)
            elif "refund" in task.lower():
                resolved_target = "refunds.py"
            elif "calc" in task.lower() or "divide" in task.lower():
                resolved_target = "calculator.py"
            else:
                resolved_target = "calculator.py"

        target_full_path = self.workspace_root / resolved_target

        original_content = ""
        if target_full_path.exists():
            original_content = target_full_path.read_text(encoding="utf-8", errors="replace")
        else:
            original_content = "# New file created by SentinelForge\n"

        # Determine proposed modification
        if code_override:
            modified_content = code_override
        else:
            # Let LLM generate the proposed code
            prompt = (
                f"Generate full corrected Python code for '{resolved_target}'.\n"
                f"Task: {task}\n"
                f"Original Code:\n{original_content}\n"
                f"Return ONLY valid python code."
            )
            llm_code = self.llm.generate(AGENT_SYSTEM_PROMPT, prompt)
            # Strip markdown code blocks if present
            if "```" in llm_code:
                lines = llm_code.splitlines()
                code_lines = [l for l in lines if not l.startswith("```")]
                modified_content = "\n".join(code_lines).strip() + "\n"
            else:
                modified_content = llm_code

        # Call MCP propose_patch tool
        patch_res = mcp_dispatcher.call_tool(
            "propose_patch",
            {
                "target_file": resolved_target,
                "original_content": original_content,
                "modified_content": modified_content,
                "rationale": f"Address task: {task}",
            },
        )

        patch_id = patch_res.get("patch_id")
        unified_diff = patch_res.get("unified_diff")

        # --- Stage 5: Sandbox Execution in Isolated Scratch Space ---
        # Fail-safe: Original repository is NEVER directly mutated during testing.
        sandbox_executed = False
        sandbox_success = False
        test_summary: Dict[str, Any] = {}
        raw_test_output = ""

        with tempfile.TemporaryDirectory() as scratch_dir:
            scratch_path = Path(scratch_dir)

            # Copy existing workspace into temporary scratch directory
            if self.workspace_root.exists():
                for item in self.workspace_root.iterdir():
                    if item.name.startswith("."):
                        continue
                    dest = scratch_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            # Apply proposed patch inside scratch directory
            staged_file = scratch_path / resolved_target
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            staged_file.write_text(modified_content, encoding="utf-8")

            # Execute tests inside sandbox via MCP execute_in_sandbox tool
            sandbox_res = mcp_dispatcher.call_tool(
                "execute_in_sandbox",
                {
                    "command": "python",
                    "args": ["-m", "unittest", "discover", "-s", str(scratch_path), "-p", "test_*.py"],
                    "timeout_seconds": 12,
                    "language": "python",
                },
            )

            sandbox_executed = True
            sandbox_success = sandbox_res.get("success", False)
            raw_test_output = f"{sandbox_res.get('stdout', '')}\n{sandbox_res.get('stderr', '')}".strip()
            test_summary = {
                "exit_code": sandbox_res.get("exit_code"),
                "duration_ms": sandbox_res.get("duration_ms"),
                "timed_out": sandbox_res.get("timed_out", False),
                "output": raw_test_output,
            }

        # --- Stage 6: Self-Critique ---
        critique_prompt = STAGE_CRITIQUE_PROMPT.format(
            diff=unified_diff,
            test_output=raw_test_output,
        )
        self_critique = self.llm.generate(AGENT_SYSTEM_PROMPT, critique_prompt)

        # --- Stage 7: Final Report ---
        risk_notes = [
            "Diff is held in PENDING_APPROVAL status. No repository changes applied yet.",
            f"Sandbox verification: {'PASSED' if sandbox_success else 'FAILED / INCOMPLETE'}.",
        ]

        if not sandbox_success:
            risk_notes.append("WARNING: Tests failed or did not exit cleanly. Human inspection required.")

        report = AgentExecutionReport(
            task=task,
            stage_reached="Stage 7: Final Report",
            plan=plan,
            citations=citations,
            patch_id=patch_id,
            target_file=resolved_target,
            unified_diff=unified_diff,
            rationale=patch_res.get("rationale"),
            sandbox_executed=sandbox_executed,
            sandbox_success=sandbox_success,
            test_summary=test_summary,
            self_critique=self_critique,
            risk_notes=risk_notes,
            status="PENDING_APPROVAL",
        )

        audit_logger.record_event(
            event_type="AGENT_LOOP_COMPLETED",
            severity="INFO" if sandbox_success else "WARNING",
            details={
                "task": task[:60],
                "patch_id": patch_id,
                "sandbox_success": sandbox_success,
            },
            success=True,
        )

        return report

