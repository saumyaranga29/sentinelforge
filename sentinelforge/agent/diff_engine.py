import ast
import difflib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from sentinelforge.config import settings
from sentinelforge.sandbox.security import SandboxSecurityValidator
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.agent.diff_engine")


def extract_public_functions(code: str) -> Set[str]:
    """Extracts top-level and class function names using AST."""
    try:
        tree = ast.parse(code)
        return {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    except Exception:
        return set()


def ensure_full_file_with_ast(original_content: str, generated_code: str) -> tuple[str, List[str]]:
    """
    Ensures modified_content is a complete, full-file representation.
    If generated_code is only a partial snippet/function, surgical-splices it
    into the original file so existing symbols (add, subtract, etc.) are never destroyed.
    Returns (full_modified_code, dropped_symbols).
    """
    if not original_content.strip():
        return generated_code, []

    orig_funcs = extract_public_functions(original_content)
    gen_funcs = extract_public_functions(generated_code)

    # Check if generator dropped functions from original
    dropped = orig_funcs - gen_funcs
    if not dropped:
        # Generated code preserves all symbols
        return generated_code, []

    # Generator returned a subset (e.g. only 1 function)
    # Perform surgical replacement of the matching defined functions
    full_code = original_content
    for func_name in gen_funcs:
        if func_name in orig_funcs:
            pattern = re.compile(
                rf"^([ \t]*)def {func_name}\b[^\n]*:.*?(?=\n\1def |\n\1class |\Z)",
                re.MULTILINE | re.DOTALL,
            )
            new_func_match = re.search(
                rf"^([ \t]*)def {func_name}\b[^\n]*:.*?(?=\n\1def |\n\1class |\Z)",
                generated_code,
                re.MULTILINE | re.DOTALL,
            )
            if new_func_match and pattern.search(full_code):
                full_code = pattern.sub(new_func_match.group(0).strip(), full_code)

    # Re-verify symbols after surgical merge
    new_funcs = extract_public_functions(full_code)
    remaining_dropped = sorted(list(orig_funcs - new_funcs))

    return full_code, remaining_dropped


class PatchProposal(BaseModel):
    """Represents a unified diff proposal awaiting human approval."""

    patch_id: str
    target_file: str
    rationale: str
    unified_diff: str
    original_content: str
    modified_content: str
    dropped_symbols: List[str] = Field(default_factory=list)
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
        """Generates a unified diff from the full file and stages it as PENDING_APPROVAL."""
        # Validate path stays in workspace
        file_path = Path(target_file)
        SandboxSecurityValidator.validate_path(file_path, self.workspace_root)
        SandboxSecurityValidator.validate_file_extension(file_path)

        # Ensure modified_content is the COMPLETE file (never naked function bodies)
        # and verify public symbols using AST
        dropped_symbols: List[str] = []
        full_modified = modified_content
        if target_file.endswith(".py") and original_content.strip():
            full_modified, dropped_symbols = ensure_full_file_with_ast(original_content, modified_content)

        # Generate standard unified diff against full original file
        orig_lines = original_content.splitlines(keepends=True)
        mod_lines = full_modified.splitlines(keepends=True)

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
            modified_content=full_modified,
            dropped_symbols=dropped_symbols,
            status="PENDING_APPROVAL",
        )

        self._active_patch = proposal

        audit_logger.record_event(
            event_type="PATCH_PROPOSED",
            severity="INFO",
            target_path=target_file,
            details={"patch_id": patch_id, "rationale": rationale, "dropped_symbols": dropped_symbols},
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

    def revert_patch(self, target_file: Optional[str] = None) -> Dict[str, Any]:
        """
        One-click restore: Reverts modified file to its safety backup (.bak).
        Guarantees instant rollback of applied changes.
        """
        resolved = target_file or (self._active_patch.target_file if self._active_patch else "calculator.py")
        target_path = (self.workspace_root / resolved).resolve()
        backup_path = target_path.with_suffix(target_path.suffix + ".bak")

        if not backup_path.exists():
            raise FileNotFoundError(f"No safety backup ({backup_path.name}) found. Cannot revert.")

        original_backup = backup_path.read_text(encoding="utf-8")
        target_path.write_text(original_backup, encoding="utf-8")

        if self._active_patch and self._active_patch.target_file == resolved:
            self._active_patch.status = "REVERTED"

        audit_logger.record_event(
            event_type="PATCH_REVERTED",
            severity="INFO",
            target_path=str(target_path),
            details={"reverted_file": resolved},
            success=True,
        )

        return {
            "status": "REVERTED",
            "file": resolved,
            "message": f"Successfully reverted {resolved} to pre-patch safety backup.",
        }


diff_engine = DiffEngine()

