import os
from pathlib import Path
from typing import List, Set
import re

from sentinelforge.utils.audit import audit_logger


class SecurityViolationError(Exception):
    """Raised when a command, path, or file breaches sandbox security invariants."""
    pass


class SandboxSecurityValidator:
    """Enforces strict path containment, command allowlists, and parameter sanitization."""

    COMMAND_ALLOWLIST: Set[str] = {
        "python",
        "pytest",
        "node",
        "npm",
    }

    SUBCOMMAND_ALLOWLIST: Set[str] = {
        "-m", "py_compile", "unittest", "pytest",
        "--test", "-c", "test"
    }

    ALLOWED_EXTENSIONS: Set[str] = {
        ".py", ".js", ".ts", ".json", ".md", ".txt", ".yaml", ".yml", ".pdf"
    }

    DANGEROUS_SHELL_CHARS = re.compile(r"[;&|`$<>]|\b(sh|bash|powershell|cmd|curl|wget|nc|chmod|rm)\b", re.IGNORECASE)

    @classmethod
    def validate_path(cls, candidate_path: Path, workspace_root: Path) -> Path:
        """
        Validates that candidate_path resolves strictly within workspace_root.
        Guards against:
          1. Path traversal attacks (../../etc/passwd, ..\\windows\\win.ini)
          2. Symlink escapes pointing outside workspace
          3. Windows 8.3 short-name aliasing mismatches
        """
        real_workspace = os.path.realpath(str(workspace_root))

        cand_str = str(candidate_path).replace("\\", "/")
        norm_cand_path = Path(cand_str)

        if not norm_cand_path.is_absolute():
            real_candidate = os.path.realpath(os.path.join(real_workspace, cand_str))
        else:
            real_candidate = os.path.realpath(str(norm_cand_path))

        norm_workspace = os.path.normcase(real_workspace)
        norm_candidate = os.path.normcase(real_candidate)

        cand_p = Path(real_candidate)
        if cand_p.is_symlink():
            target = cand_p.readlink()
            real_target = os.path.realpath(os.path.join(os.path.dirname(real_candidate), str(target)))
            if not os.path.normcase(real_target).startswith(norm_workspace):
                audit_logger.record_event(
                    event_type="SYMLINK_ESCAPE_BLOCKED",
                    severity="SECURITY_ALERT",
                    target_path=str(candidate_path),
                    details={"symlink_target": real_target},
                    success=False,
                )
                raise SecurityViolationError(
                    f"Security Error: Symlink '{candidate_path}' points outside workspace root."
                )

        is_contained = (
            norm_candidate == norm_workspace
            or norm_candidate.startswith(norm_workspace + os.sep)
            or norm_candidate.startswith(norm_workspace + "/")
        )

        if not is_contained:
            audit_logger.record_event(
                event_type="PATH_TRAVERSAL_BLOCKED",
                severity="SECURITY_ALERT",
                target_path=str(candidate_path),
                details={"resolved_path": real_candidate},
                success=False,
            )
            raise SecurityViolationError(
                f"Security Error: Path traversal attempt blocked. '{candidate_path}' resolves outside workspace."
            )

        return Path(real_candidate)

    @classmethod
    def validate_file_extension(cls, file_path: Path) -> None:
        """Validates that file extension is in the safe allowlist."""
        suffix = file_path.suffix.lower()
        if suffix and suffix not in cls.ALLOWED_EXTENSIONS:
            audit_logger.record_event(
                event_type="INVALID_FILE_EXTENSION",
                severity="WARNING",
                target_path=str(file_path),
                details={"extension": suffix},
                success=False,
            )
            raise SecurityViolationError(
                f"Security Error: File type '{suffix}' is not permitted in sandbox."
            )

    @classmethod
    def validate_command(cls, command: str, args: List[str]) -> None:
        """
        Validates that the command and its arguments are within strict allowlist boundaries.
        Guards against shell injections, arbitrary binary executions, and chained scripts.
        """
        base_cmd = Path(command).name.lower()
        if base_cmd.endswith(".exe"):
            base_cmd = base_cmd[:-4]

        if base_cmd not in cls.COMMAND_ALLOWLIST:
            audit_logger.record_event(
                event_type="UNAUTHORIZED_COMMAND_BLOCKED",
                severity="SECURITY_ALERT",
                command=f"{command} {' '.join(args)}",
                details={"base_cmd": base_cmd},
                success=False,
            )
            raise SecurityViolationError(
                f"Security Error: Command '{base_cmd}' is not in the sandbox allowlist ({cls.COMMAND_ALLOWLIST})."
            )

        full_invocation = f"{command} {' '.join(args)}"
        if cls.DANGEROUS_SHELL_CHARS.search(full_invocation):
            audit_logger.record_event(
                event_type="COMMAND_INJECTION_BLOCKED",
                severity="SECURITY_ALERT",
                command=full_invocation,
                success=False,
            )
            raise SecurityViolationError(
                "Security Error: Disallowed shell metacharacters or dangerous binaries detected in command arguments."
            )

