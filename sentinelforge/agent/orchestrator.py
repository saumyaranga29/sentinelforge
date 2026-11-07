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
    can_approve: bool = True
    regression_detected: bool = False
    baseline_passed: bool = True
    newly_failing_tests: List[str] = Field(default_factory=list)
    dropped_symbols: List[str] = Field(default_factory=list)


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

        repo_inspection = mcp_dispatcher.call_tool("inspect_repository", {"relative_path": ""})
        analysis_prompt = STAGE_ANALYSIS_PROMPT.format(
            task=task,
            repo_files=str(repo_inspection.get("tree", [])[:10]),
        )
        task_analysis = self.llm.generate(AGENT_SYSTEM_PROMPT, analysis_prompt)

        plan_prompt = STAGE_PLAN_PROMPT.format(task=task, analysis=task_analysis)
        plan = self.llm.generate(AGENT_SYSTEM_PROMPT, plan_prompt)

        retrieval_res = mcp_dispatcher.call_tool(
            "retrieve_context",
            {"query": task, "top_k": 3},
        )
        citations = retrieval_res.get("results", [])

        resolved_target = target_file
        if not resolved_target:
            import re
            py_match = re.search(r'\b([a-zA-Z0-9_\-]+\.py)\b', task)
            if py_match:
                resolved_target = py_match.group(1)
            elif any(w in task.lower() for w in ["auth", "password", "token", "login", "credential"]):
                resolved_target = "auth.py"
            elif "refund" in task.lower():
                resolved_target = "refunds.py"
            elif any(w in task.lower() for w in ["calc", "divide", "arithmetic", "math"]):
                resolved_target = "calculator.py"
            elif citations:
                top_src = citations[0].get("source_file", "")
                stem = Path(top_src).stem.replace("_spec", "").replace("_policy", "")
                resolved_target = f"{stem}.py"
            else:
                resolved_target = "calculator.py"

        target_full_path = self.workspace_root / resolved_target

        original_content = ""
        if target_full_path.exists():
            original_content = target_full_path.read_text(encoding="utf-8", errors="replace")
        else:
            original_content = "# New file created by SentinelForge\n"

        if code_override:
            modified_content = code_override
        else:
            prompt = (
                f"Generate full corrected Python code for '{resolved_target}'.\n"
                f"Task: {task}\n"
                f"Original Code:\n{original_content}\n"
                f"Return ONLY valid python code."
            )
            llm_code = self.llm.generate(AGENT_SYSTEM_PROMPT, prompt)
            if "```" in llm_code:
                lines = llm_code.splitlines()
                code_lines = [l for l in lines if not l.startswith("```")]
                modified_content = "\n".join(code_lines).strip() + "\n"
            else:
                modified_content = llm_code

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

        sandbox_executed = False
        sandbox_success = False
        baseline_success = False
        baseline_output = ""
        newly_failing_tests: List[str] = []
        raw_test_output = ""
        test_summary: Dict[str, Any] = {}

        dropped_symbols = patch_res.get("dropped_symbols", [])
        effective_modified_content = patch_res.get("modified_content", modified_content)

        def parse_test_failures(output: str) -> List[str]:
            import re
            return re.findall(r"(?:FAIL|ERROR):\s+([a-zA-Z0-9_\.]+)", output)

        with tempfile.TemporaryDirectory() as scratch_dir:
            scratch_path = Path(scratch_dir)

            if self.workspace_root.exists():
                for item in self.workspace_root.iterdir():
                    if item.name.startswith("."):
                        continue
                    dest = scratch_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            target_stem = Path(resolved_target).stem
            test_pattern = f"test_{target_stem}.py"

            if resolved_target == "calculator.py" and ("return 0" in task.lower() or "returns 0" in task.lower()):
                test_file = scratch_path / "test_calculator.py"
                test_file.write_text(
                    "import unittest\n"
                    "from calculator import divide\n\n"
                    "class TestCalculatorZero(unittest.TestCase):\n"
                    "    def test_divide_valid(self):\n"
                    "        self.assertEqual(divide(10, 2), 5)\n\n"
                    "    def test_divide_zero_returns_zero(self):\n"
                    "        self.assertEqual(divide(1, 0), 0.0)\n\n"
                    "if __name__ == '__main__':\n"
                    "    unittest.main()\n",
                    encoding="utf-8",
                )
            elif resolved_target == "auth.py" and not (scratch_path / "test_auth.py").exists():
                test_file = scratch_path / "test_auth.py"
                test_file.write_text(
                    "import unittest\n"
                    "from auth import validate_password\n\n"
                    "class TestAuth(unittest.TestCase):\n"
                    "    def test_valid_password(self):\n"
                    "        self.assertTrue(validate_password('SecretPass1'))\n\n"
                    "    def test_short_password(self):\n"
                    "        self.assertFalse(validate_password('short1'))\n\n"
                    "    def test_no_digit(self):\n"
                    "        self.assertFalse(validate_password('SecretPassword'))\n\n"
                    "if __name__ == '__main__':\n"
                    "    unittest.main()\n",
                    encoding="utf-8",
                )

            matching_test = scratch_path / test_pattern
            if matching_test.exists():
                test_args = ["-m", "unittest", "discover", "-s", str(scratch_path), "-p", test_pattern]
            else:
                test_args = ["-m", "unittest", "discover", "-s", str(scratch_path), "-p", "test_*.py"]

            baseline_res = mcp_dispatcher.call_tool(
                "execute_in_sandbox",
                {
                    "command": "python",
                    "args": test_args,
                    "timeout_seconds": 12,
                    "language": "python",
                },
            )
            baseline_success = baseline_res.get("success", False)
            baseline_output = f"{baseline_res.get('stdout', '')}\n{baseline_res.get('stderr', '')}".strip()
            baseline_failures = set(parse_test_failures(baseline_output))

            staged_file = scratch_path / resolved_target
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            staged_file.write_text(effective_modified_content, encoding="utf-8")

            sandbox_res = mcp_dispatcher.call_tool(
                "execute_in_sandbox",
                {
                    "command": "python",
                    "args": test_args,
                    "timeout_seconds": 12,
                    "language": "python",
                },
            )

            sandbox_executed = True
            sandbox_success = sandbox_res.get("success", False)
            raw_test_output = f"{sandbox_res.get('stdout', '')}\n{sandbox_res.get('stderr', '')}".strip()
            post_failures = set(parse_test_failures(raw_test_output))
            newly_failing_tests = sorted(list(post_failures - baseline_failures))

            test_summary = {
                "exit_code": sandbox_res.get("exit_code"),
                "duration_ms": sandbox_res.get("duration_ms"),
                "timed_out": sandbox_res.get("timed_out", False),
                "output": raw_test_output,
                "baseline_passed": baseline_success,
                "baseline_output": baseline_output,
                "newly_failing_tests": newly_failing_tests,
            }

        critique_prompt = STAGE_CRITIQUE_PROMPT.format(
            diff=unified_diff,
            test_output=raw_test_output,
        )
        self_critique = self.llm.generate(AGENT_SYSTEM_PROMPT, critique_prompt)

        regression_detected = (not sandbox_success) or bool(newly_failing_tests) or bool(dropped_symbols)
        can_approve = sandbox_success and (len(newly_failing_tests) == 0) and (len(dropped_symbols) == 0)

        risk_notes = [
            "Diff is held in PENDING_APPROVAL status. No repository changes applied yet.",
            f"Baseline tests (pre-patch): {'PASSED' if baseline_success else 'FAILED / UNVERIFIED'}.",
            f"Sandbox verification (post-patch): {'PASSED' if sandbox_success else 'FAILED / REGRESSION'}.",
        ]

        if newly_failing_tests:
            risk_notes.append(f"REGRESSION DETECTED: Newly failing tests: {', '.join(newly_failing_tests)}.")
        if dropped_symbols:
            risk_notes.append(f"AST INTEGRITY VIOLATION: Public functions dropped without instruction: {', '.join(dropped_symbols)}.")
        if not can_approve:
            risk_notes.append("APPROVAL GATE BLOCKED: Automated approval is disabled due to sandbox test failure or symbol regression.")

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
            can_approve=can_approve,
            regression_detected=regression_detected,
            baseline_passed=baseline_success,
            newly_failing_tests=newly_failing_tests,
            dropped_symbols=dropped_symbols,
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

