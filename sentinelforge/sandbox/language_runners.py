import re
from pathlib import Path
from typing import Dict, Optional
from pydantic import BaseModel, Field

from sentinelforge.sandbox.runner import SandboxRunner, SandboxResult


class TestWorkflowResult(BaseModel):
    """Normalized test report across languages."""

    language: str
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    execution_success: bool = False
    raw_output: str = ""
    error_summary: Optional[str] = None
    duration_ms: float = 0.0


class PythonTestWorkflow:
    """Manages Python test execution and syntax verification inside sandbox."""

    def __init__(self, sandbox_runner: SandboxRunner):
        self.runner = sandbox_runner

    def run_tests(self, test_path: Optional[str] = None, timeout_seconds: int = 15) -> TestWorkflowResult:
        """Executes unittest or pytest inside sandbox and parses test results."""
        args = ["-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]
        if test_path:
            args = ["-m", "unittest", test_path]

        res: SandboxResult = self.runner.execute(
            command="python",
            args=args,
            timeout_seconds=timeout_seconds,
        )

        output = f"{res.stdout}\n{res.stderr}".strip()
        total, passed, failed = self._parse_unittest_output(output, res.exit_code)

        return TestWorkflowResult(
            language="python",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            execution_success=(res.exit_code == 0),
            raw_output=output,
            error_summary=res.stderr if res.exit_code != 0 else None,
            duration_ms=res.duration_ms,
        )

    def verify_syntax(self, file_path: str) -> SandboxResult:
        """Runs py_compile to ensure valid syntax before running."""
        return self.runner.execute(
            command="python",
            args=["-m", "py_compile", file_path],
        )

    def _parse_unittest_output(self, output: str, exit_code: int) -> tuple[int, int, int]:
        """Extracts test metrics from unittest stdout/stderr."""
        # e.g., "Ran 5 tests in 0.012s"
        ran_match = re.search(r"Ran (\d+) test", output)
        total = int(ran_match.group(1)) if ran_match else 0

        failed = 0
        if "FAILED (" in output:
            fail_match = re.search(r"failures=(\d+)", output)
            err_match = re.search(r"errors=(\d+)", output)
            if fail_match:
                failed += int(fail_match.group(1))
            if err_match:
                failed += int(err_match.group(1))
            if failed == 0 and exit_code != 0:
                failed = total or 1

        passed = total - failed if total >= failed else (total if exit_code == 0 else 0)
        return total, passed, failed


class JavaScriptTestWorkflow:
    """Manages JavaScript/Node test execution (Bonus Language Support)."""

    def __init__(self, sandbox_runner: SandboxRunner):
        self.runner = sandbox_runner

    def run_tests(self, test_file: Optional[str] = None) -> TestWorkflowResult:
        """Runs node test runner inside sandbox."""
        args = ["--test"]
        if test_file:
            args.append(test_file)

        res: SandboxResult = self.runner.execute(
            command="node",
            args=args,
        )

        output = f"{res.stdout}\n{res.stderr}".strip()
        # Parse node:test output
        pass_match = re.findall(r"✔", output)
        fail_match = re.findall(r"✖", output)

        passed = len(pass_match)
        failed = len(fail_match)
        total = passed + failed

        return TestWorkflowResult(
            language="javascript",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            execution_success=(res.exit_code == 0),
            raw_output=output,
            error_summary=res.stderr if res.exit_code != 0 else None,
            duration_ms=res.duration_ms,
        )

