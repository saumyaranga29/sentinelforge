# 05. Sandboxed Code-Gen Agent, Cognitive Loop & Diff Engine

## 1. Cognitive Architecture & State Machine

The Agent Orchestrator implements a deterministic 7-stage state machine enforcing the required workflow:

```
[Task Analysis] ──► [Plan Generation] ──► [Context Retrieval (MCP)]
                                                     │
                                                     ▼
[Final Report] ◄── [Self-Critique] ◄── [Sandbox Execution (MCP)] ◄── [Patch Proposal (MCP)]
      │
      ▼
[Human Approval Gate (PENDING_APPROVAL)]
      ├── Approved ──► [Apply Patch + Create .bak Backup]
      └── Rejected ──► [Discard Proposal]
```

### Key Safety Invariants:
1. **Isolated Scratch Workspace**: During sandbox verification (Stage 5), the agent clones the workspace into an ephemeral directory (`tempfile.TemporaryDirectory`). The patch is applied inside the clone, and tests run there. The actual live repository is **never modified** during testing.
2. **Unified Diff Format**: Code edits are strictly formulated as `diff -u` patches (`--- a/file.py \n +++ b/file.py`), making them readable and reviewable by human evaluators.
3. **Zero Silent Mutation**: All proposed diffs enter `PENDING_APPROVAL` status. Files on disk are only modified when the user calls `/api/agent/patch/approve` with `approved=true`.
4. **Fail Safely**: If tests fail inside the sandbox, the agent never fabricates success. The failure exit code, stdout, and stderr are captured and exposed in the `test_summary`, and `risk_notes` flag that human inspection is required.

---

## 2. Senior Technical Interview & Defense Questions

### Question 1: "Why do you run sandbox tests in a cloned scratch workspace instead of in-place?"
**Candidate Answer**:
> "If the agent applies an untested patch directly to the active workspace to run tests, and those tests fail or cause side effects, the repository is left in a broken, half-migrated state. By cloning the repository into an isolated scratch directory, applying the patch there, and executing test suites inside the scratch jail, the live repository remains completely pristine. Only after the tests pass AND the human explicitly approves the change is the patch applied to the live repository, with an automatic `.bak` backup."

### Question 2: "What is the purpose of the Self-Critique stage?"
**Candidate Answer**:
> "The self-critique stage acts as an automated second pair of eyes before presenting the report to the user. It takes the proposed unified diff and the actual sandbox test execution logs and evaluates:
> 1. Did the tests actually pass, or did they fail / time out?
> 2. Does the diff introduce security flaws (e.g. unvalidated inputs, shell injections)?
> 3. Are there residual regression risks?
> This step ensures that if tests failed, the agent honestly critiques the outcome rather than hallucinating that the fix succeeded."

### Question 3: "How does SentinelForge defend against hallucinations where the agent claims tests passed when they didn't?"
**Candidate Answer**:
> "The assessment rubric penalizes submissions that claim tests passed when they did not. SentinelForge guarantees test truthfulness through programmatic verification:
> - `sandbox_success` is computed directly from the OS process return code: `(res.exit_code == 0) and not timed_out`.
> - If `exit_code != 0`, `sandbox_success` is `False`, and `risk_notes` automatically appends: `'WARNING: Tests failed or did not exit cleanly. Human inspection required.'`
> - The actual raw test stdout and stderr are preserved verbatim in `test_summary.output` so the evaluator can verify the exact test runner output."

---

## 3. Live Defense / Live Modification Scenarios

### Scenario A: "Demonstrate that the repository is never modified before explicit approval."
* **Command to Run**: `.\.venv\Scripts\pytest.exe tests/test_agent_loop.py -v`
* **File to Open**: [`sentinelforge/agent/orchestrator.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/agent/orchestrator.py) and [`sentinelforge/agent/diff_engine.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/agent/diff_engine.py)
* **Explanation**: Show `test_zero_silent_mutation_invariant`. Demonstrate that `calculator.py` on disk has identical file contents before and after the agent runs. Then show `test_explicit_approval_applies_patch`, showing the file only updates after `diff_engine.apply_patch(..., approved=True)` is called.

### Scenario B: "How do you roll back an applied patch if something goes wrong?"
* **File to Open**: [`sentinelforge/agent/diff_engine.py`](file:///c:/Users/Saumya%20Ranga/OneDrive%20-%20UPES/Desktop/Dexter/sentinelforge/agent/diff_engine.py)
* **Explanation**: Show lines 88-92 where `target_path.with_suffix(target_path.suffix + '.bak')` is written before modifying the target file. To restore, simply overwrite the target file with the `.bak` backup.
