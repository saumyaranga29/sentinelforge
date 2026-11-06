# 04. Sandboxed Execution Engine & Security Isolation

## 1. Security Architecture & Threat Mitigations

### Threat Modeling Matrix

| Threat | Attack Vector | SentinelForge Defensive Control | Implemented In |
| :--- | :--- | :--- | :--- |
| **Path Traversal** | `../../etc/passwd` or `..\windows\win.ini` | Canonical path resolution (`os.path.realpath`, `normcase`) verified strictly relative to workspace root | [`security.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/security.py) |
| **Symlink Escape** | Symlink created pointing to `/root` or `C:\` | Destination path resolution; symlink targets pointing outside workspace trigger immediate security abort | [`security.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/security.py) |
| **Command Injection** | `python; rm -rf /` or `pytest \| nc` | Shell metacharacter regex filter (`;&\|\`$<>`) + execution with `shell=False` | [`security.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/security.py) |
| **Arbitrary Binaries** | `curl`, `wget`, `bash`, `powershell` | Strict allowlist: only `python`, `pytest`, `node`, `npm` allowed | [`security.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/security.py) |
| **Infinite Loops / DoS** | `while True: pass` or `sleep(100)` | Subprocess execution timeout (default 10s); process killed with exit code -9 | [`runner.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/runner.py) |
| **Log Bomb / RAM Exhaust** | Printing 1GB to stdout | Stream buffer cap at 50KB (`sandbox_max_output_bytes`); outputs cleanly truncated | [`runner.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/runner.py) |
| **Secret Exfiltration** | Script reading host environment variables | Minimal scrubbed environment: drops all cloud credentials, tokens, and API keys | [`runner.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/runner.py) |
| **Silent Mutation** | Agent modifies code without consent | All changes staged as unified diffs in `PENDING_APPROVAL` status | [`diff_engine.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/agent/diff_engine.py) |

---

## 2. Senior Technical Interview & Defense Questions

### Question 1: "Why did you use `shell=False` in `subprocess.run()`, and how does that prevent command injection?"
**Candidate Answer**:
> "When `shell=True` is used, the command string is passed directly to the system shell (`/bin/sh` on Linux or `cmd.exe` on Windows). The shell parses metacharacters like semicolons, pipes, and backticks, allowing an attacker to chain arbitrary commands (e.g. `python script.py; rm -rf /`). By setting `shell=False` and passing commands as an explicit array of arguments `[executable, arg1, arg2]`, the operating system invokes the binary directly via `execve` or `CreateProcess` without spawning a shell interpreter. In addition, our `SandboxSecurityValidator` inspects all arguments with regex to reject shell metacharacters before execution."

### Question 2: "How do you defend against path traversal on Windows where 8.3 short names and case sensitivity differ?"
**Candidate Answer**:
> "On Windows, a directory path like `C:\Users\Saumya Ranga` can be aliased as `C:\Users\SAUMYA~1`. Standard Python `pathlib.Path.is_relative_to()` will fail or be bypassed if one path uses the short-name alias and the other uses the full name. SentinelForge solves this by:
> 1. Resolving both candidate path and workspace root using `os.path.realpath()`, which expands all Windows 8.3 short-name aliases and resolves symlinks.
> 2. Normalizing case using `os.path.normcase()`.
> 3. Verifying that the candidate path strictly starts with the workspace root plus the path separator. Any path escaping the boundary raises a `SecurityViolationError` and logs a security audit event."

### Question 3: "Why did you support JavaScript/Node.js in addition to Python?"
**Candidate Answer**:
> "Supporting a second language workflow was a key bonus engineering capability (+2 points). We built `JavaScriptTestWorkflow` in `sentinelforge/sandbox/language_runners.py` to run Node.js native test runner (`node --test`) and syntax compilation (`node -c`). The same path jails, command allowlists, and timeout monitors apply uniformly to both Python and JavaScript workflows."

---

## 3. Live Defense / Live Modification Scenarios

### Scenario A: "Prove in a live terminal that path traversal and unauthorized commands are rejected."
* **Command to Run**: `.\.venv\Scripts\pytest.exe tests/test_sandbox_security.py -v`
* **File to Open**: [`sentinelforge/sandbox/security.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/security.py)
* **Explanation**: Show `test_path_traversal_blocked`, `test_windows_path_traversal_blocked`, and `test_unauthorized_command_blocked`. Point to the `audit_logger.record_event()` calls recording each blocked intrusion attempt.

### Scenario B: "How do you handle a runaway infinite-loop script?"
* **File to Open**: [`sentinelforge/sandbox/runner.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/sandbox/runner.py)
* **Explanation**: Walk through lines 75-95. Show how `subprocess.TimeoutExpired` catches the timeout, terminates the process group, sets `exit_code = -9, timed_out = True`, and logs a warning event so the agent is informed of the failure safely.

