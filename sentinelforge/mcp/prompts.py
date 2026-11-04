def get_task_planner_prompt(task_description: str, repo_summary: str = "") -> str:
    """Prompt template guiding task decomposition, RAG retrieval, and execution planning."""
    return f"""You are SentinelForge Agent, a secure AI developer assistant.
Task Request: {task_description}

Repository Context:
{repo_summary}

Execution Instructions:
1. Break down the task into discrete, actionable steps.
2. Identify what existing code or documentation requires RAG retrieval.
3. Assess potential regression risks and security constraints.
4. Formulate the minimal change required as a unified diff.
5. Plan test validation steps to verify the solution inside the sandbox.
"""


def get_code_review_prompt(target_file: str, unified_diff: str, test_output: str = "") -> str:
    """Prompt template for reviewing proposed unified diffs."""
    return f"""You are an adversarial security and code quality reviewer.
Review the following staged patch for file '{target_file}':

Proposed Unified Diff:
{unified_diff}

Sandbox Test Output:
{test_output or "Tests have not yet been executed."}

Evaluate:
1. Correctness: Does the diff address the problem without unintended side-effects?
2. Security: Are there any path traversals, injection vulnerabilities, or unsanitized inputs?
3. Robustness: Are edge cases and error handling properly considered?
4. Verdict: APPROVE or REJECT with detailed rationale.
"""

