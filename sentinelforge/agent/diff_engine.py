import difflib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from sentinelforge.config import settings
from sentinelforge.sandbox.security import SandboxSecurityValidator
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.agent.diff_engine")


class PatchProposal(BaseModel):
    """Represents a unified diff proposal awaiting human approval."""

    patch_id: str
    target_file: str
    rationale: str
    unified_diff: str
    original_content: str
    modified_content: str
    status: str = "PENDING_APPROVAL"  # PENDING_APPROVAL, APPROVED, REJECTED, APPLIED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DiffEngine:
    """
    Manages unified diff generation, inspection, staging, and explicit human approval.
    Enforces the zero-silent-mutation security invariant.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or settings.workspace_root).resolve()
        self._active_patch: Optional[PatchProposal] = None

    @property
    def active_patch(self) -> Optional[PatchProposal]:
        return self._active_patch

    def create_patch(
        self,
        target_file: str,
        original_content: str,
        modified_content: str,
        rationale: str,
    ) -> PatchProposal:
        """Generates a unified diff and stages it as PENDING_APPROVAL."""
        # Validate path stays in workspace
        file_path = Path(target_file)
        SandboxSecurityValidator.validate_path(file_path, self.workspace_root)
        SandboxSecurityValidator.validate_file_extension(file_path)

        # Generate standard unified diff
        orig_lines = original_content.splitlines(keepends=True)
        mod_lines = modified_content.splitlines(keepends=True)

        diff = "".join(
            difflib.unified_diff(
                orig_lines,
                mod_lines,
                fromfile=f"a/{target_file}",
                tofile=f"b/{target_file}",
                lineterm="\n",
            )
        )

        patch_id = f"patch_{int(datetime.now(timezone.utc).timestamp())}"
        proposal = PatchProposal(
            patch_id=patch_id,
            target_file=target_file,
            rationale=rationale,
            unified_diff=diff,
            original_content=original_content,
            modified_content=modified_content,
            status="PENDING_APPROVAL",
        )

        self._active_patch = proposal

        audit_logger.record_event(
            event_type="PATCH_PROPOSED",
            severity="INFO",
            target_path=target_file,
            details={"patch_id": patch_id, "rationale": rationale},
            success=True,
        )

        return proposal

    def apply_patch(self, patch_id: str, approved: bool) -> bool:
        """
        Applies staged patch ONLY if explicitly approved by human user.
        Preserves original repository state and creates backup.
        """
        if not self._active_patch or self._active_patch.patch_id != patch_id:
            raise ValueError(f"No active patch found with ID '{patch_id}'.")

        if not approved:
            self._active_patch.status = "REJECTED"
            audit_logger.record_event(
                event_type="PATCH_REJECTED",
                severity="INFO",
                target_path=self._active_patch.target_file,
                details={"patch_id": patch_id},
                success=True,
            )
            return False

        # Human approved: Apply patch safely
        self._active_patch.status = "APPROVED"
        target_path = (self.workspace_root / self._active_patch.target_file).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if file already exists
        if target_path.exists():
            backup_path = target_path.with_suffix(target_path.suffix + ".bak")
            backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")

        # Write modified content
        target_path.write_text(self._active_patch.modified_content, encoding="utf-8")
        self._active_patch.status = "APPLIED"

        audit_logger.record_event(
            event_type="PATCH_APPLIED",
            severity="INFO",
            target_path=str(target_path),
            details={"patch_id": patch_id},
            success=True,
        )

        return True


diff_engine = DiffEngine()

