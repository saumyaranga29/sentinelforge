# AI-Assisted Development Disclosure (AI_USAGE.md)

**Project**: SentinelForge — Privacy-first AI developer platform  
**Role**: AI/ML Engineer Technical Assessment (Dexter Platform LLC)  
**Author**: Candidate  
**Date**: November 2026  

---

## 1. Tools and Models Used
- **AI Coding Assistant**: Antigravity (Powered by Gemini 3.8 Flash)
- **Primary IDE**: Visual Studio Code / Antigravity IDE

---

## 2. Major Areas of AI Assistance
1. **Boilerplate and Interface Generation**:
   - Setting up initial Pydantic v2 schemas and FastAPI router boilerplate.
   - Initializing unified diff formatting with Python's standard `difflib`.
2. **Adversarial Test Pattern Synthesis**:
   - Formulating common prompt injection signatures (`[INST]`, `<<SYS>>`, `DAN mode`, `ignore previous instructions`).
   - Defining golden query test cases for the in-repo retrieval benchmark.
3. **Configuration & Workflow Templates**:
   - Generating GitHub Actions workflow syntax for CI/CD.
   - Structuring Dockerfile and compose configurations.

---

## 3. Representative Prompts & Workflows
- *"Structure a 7-stage cognitive loop for a code generation agent adhering to the state progression: Task Analysis -> Plan -> Retrieval -> Patch Proposal -> Sandbox Execution -> Self-Critique -> Final Report."*
- *"Implement a strict filesystem jail validator ensuring canonical path resolution stays relative to workspace_root and blocks symlinks pointing outside."*
- *"Implement an in-memory fallback embedding and vector search calculation for zero-dependency test reproducibility."*

---

## 4. Independently Designed, Implemented & Verified Components
- **Architecture & Security Boundaries**:
  - All security validation policies (`SandboxSecurityValidator`), including path containment, process timeouts, command allowlists, and output truncation limits.
  - The zero-silent-mutation human approval gate (`DiffEngine`), ensuring no file is ever modified without explicit user sign-off.
- **RAG Privacy & Injection Defense**:
  - The UUID-boundary delimiter encapsulation (`PromptInjectionGuard`) ensuring retrieved context is strictly isolated from LLM instruction flow.
  - Citation tracking preserving exact line numbers, page numbers, and SHA-256 deduplication hashes.
- **MCP Protocol Conformance**:
  - Design of all 7 MCP tools, 2 resources, and 2 reusable prompts, verified via direct integration tests.
- **Code Review & Testing**:
  - Every line of code was reviewed, validated against adversarial conditions, and tested with automated unit and integration tests.

