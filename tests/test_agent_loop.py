from pathlib import Path
from sentinelforge.agent.diff_engine import DiffEngine
from sentinelforge.agent.orchestrator import AgentOrchestrator
from sentinelforge.agent.providers import MockLLMProvider


def test_agent_7_stage_execution(temp_workspace):
    """Verifies that the agent executes the full 7-stage cognitive loop."""
    orchestrator = AgentOrchestrator(
        workspace_root=temp_workspace,
        llm_provider=MockLLMProvider(),
    )

    report = orchestrator.run(
        task="Add divide by zero validation to calculator.py",
        target_file="calculator.py",
    )

    assert report.stage_reached == "Stage 7: Final Report"
    assert report.plan != ""
    assert report.unified_diff is not None
    assert "--- a/calculator.py" in report.unified_diff
    assert report.sandbox_executed is True
    assert report.status == "PENDING_APPROVAL"
    assert len(report.risk_notes) > 0


def test_zero_silent_mutation_invariant(temp_workspace):
    """Verifies that the original file is NEVER silently modified before approval."""
    calc_path = temp_workspace / "calculator.py"
    initial_content = calc_path.read_text(encoding="utf-8")

    orchestrator = AgentOrchestrator(
        workspace_root=temp_workspace,
        llm_provider=MockLLMProvider(),
    )

    report = orchestrator.run(task="Modify calculator logic")

    # Invariant check: Disk file content must be exactly identical to before the agent ran
    current_content = calc_path.read_text(encoding="utf-8")
    assert current_content == initial_content


def test_explicit_approval_applies_patch(test_diff_engine, temp_workspace):
    """Verifies human approval applies the staged patch and creates a safety backup."""
    calc_path = temp_workspace / "calculator.py"
    orig_content = calc_path.read_text(encoding="utf-8")
    new_content = orig_content + "\ndef power(a, b):\n    return a ** b\n"

    proposal = test_diff_engine.create_patch(
        target_file="calculator.py",
        original_content=orig_content,
        modified_content=new_content,
        rationale="Add power function",
    )

    assert proposal.status == "PENDING_APPROVAL"

    # Human approves patch
    applied = test_diff_engine.apply_patch(proposal.patch_id, approved=True)
    assert applied is True
    assert proposal.status == "APPLIED"

    # Verify target file updated
    updated_content = calc_path.read_text(encoding="utf-8")
    assert "def power(a, b):" in updated_content

    # Verify backup created
    backup_file = temp_workspace / "calculator.py.bak"
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == orig_content


def test_human_rejection_preserves_repo(test_diff_engine, temp_workspace):
    """Verifies that rejecting a proposal leaves the repository intact."""
    calc_path = temp_workspace / "calculator.py"
    orig_content = calc_path.read_text(encoding="utf-8")

    proposal = test_diff_engine.create_patch(
        target_file="calculator.py",
        original_content=orig_content,
        modified_content="malicious change",
        rationale="Unwanted edit",
    )

    applied = test_diff_engine.apply_patch(proposal.patch_id, approved=False)
    assert applied is False
    assert proposal.status == "REJECTED"
    assert calc_path.read_text(encoding="utf-8") == orig_content

