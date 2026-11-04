import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from sentinelforge.config import settings
from sentinelforge.sandbox.security import SandboxSecurityValidator, SecurityViolationError
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.sandbox.runner")


class SandboxResult(BaseModel):
    """Structured result returned by sandboxed execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    truncated: bool = False
    command: str
    success: bool


class SandboxRunner:
    """Executes commands inside an isolated environment with strict resource and path controls."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or settings.workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _get_scrubbed_env(self) -> Dict[str, str]:
        """
        Builds a minimal, scrubbed environment with zero credentials or cloud secrets.
        Explicitly removes sensitive variables (API keys, tokens, AWS credentials).
        """
        safe_keys = {
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "LANG",
            "LC_ALL",
            "PYTHONPATH",
        }

        scrubbed = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}

        # Keep minimal safe PATH pointing to Python and system binaries
        safe_path_elements = [
            str(Path(sys.executable).parent),
            os.environ.get("SYSTEMROOT", "C:\\Windows") + "\\system32",
            "/usr/bin",
            "/bin",
            "/usr/local/bin",
        ]
        scrubbed["PATH"] = os.pathsep.join([p for p in safe_path_elements if os.path.exists(p)])
        scrubbed["PYTHONUNBUFFERED"] = "1"
        scrubbed["PYTHONDONTWRITEBYTECODE"] = "1"

        # Explicitly ensure network isolation indicator
        if not settings.sandbox_allow_network:
            scrubbed["NO_PROXY"] = "*"
            scrubbed["http_proxy"] = "http://127.0.0.1:0"
            scrubbed["https_proxy"] = "http://127.0.0.1:0"

        return scrubbed

    def execute(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        timeout_seconds: Optional[int] = None,
    ) -> SandboxResult:
        """
        Executes a validated command within the sandbox workspace.
        """
        args = args or []
        timeout = timeout_seconds or settings.sandbox_timeout_seconds
        working_dir = self.workspace_root if cwd is None else cwd

        # 1. Security Validations
        validated_cwd = SandboxSecurityValidator.validate_path(working_dir, self.workspace_root)
        SandboxSecurityValidator.validate_command(command, args)

        # 2. Resolve executable
        full_command = [command] + args
        if command == "python":
            full_command[0] = sys.executable

        start_time = time.perf_counter()
        timed_out = False
        truncated = False
        exit_code = -1
        stdout_str = ""
        stderr_str = ""

        try:
            # Execute without shell (shell=False prevents shell injection attacks)
            process = subprocess.run(
                full_command,
                cwd=str(validated_cwd),
                env=self._get_scrubbed_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            exit_code = process.returncode
            stdout_str = process.stdout
            stderr_str = process.stderr

        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -9
            stdout_str = exc.stdout or "" if isinstance(exc.stdout, str) else ""
            stderr_str = f"Execution timed out after {timeout} seconds."
            audit_logger.record_event(
                event_type="SANDBOX_TIMEOUT",
                severity="WARNING",
                command=" ".join(full_command),
                details={"timeout_seconds": timeout},
                success=False,
            )

        except Exception as exc:
            exit_code = -1
            stderr_str = f"Sandbox execution error: {str(exc)}"
            audit_logger.record_event(
                event_type="SANDBOX_ERROR",
                severity="WARNING",
                command=" ".join(full_command),
                details={"error": str(exc)},
                success=False,
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 3. Output stream size guard
        max_bytes = settings.sandbox_max_output_bytes
        if len(stdout_str) > max_bytes:
            stdout_str = stdout_str[:max_bytes] + f"\n[OUTPUT TRUNCATED: Exceeded {max_bytes} bytes limit]"
            truncated = True

        if len(stderr_str) > max_bytes:
            stderr_str = stderr_str[:max_bytes] + f"\n[OUTPUT TRUNCATED: Exceeded {max_bytes} bytes limit]"
            truncated = True

        success = (exit_code == 0) and not timed_out

        result = SandboxResult(
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_ms=duration_ms,
            timed_out=timed_out,
            truncated=truncated,
            command=" ".join(full_command),
            success=success,
        )

        audit_logger.record_event(
            event_type="SANDBOX_EXECUTION",
            severity="INFO" if success else "WARNING",
            command=result.command,
            details={
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "truncated": truncated,
            },
            success=success,
        )

        return result

