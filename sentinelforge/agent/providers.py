import json
import httpx
from typing import Dict, List, Optional
from sentinelforge.config import settings
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.agent.providers")


class BaseLLMProvider:
    """Abstract interface for LLM inference providers."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    async def a_generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic zero-cost mock provider for unit tests, offline development,
    and fast CI/CD validation. Guaranteed to work with INR 0 cost.
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Check what stage or task is being requested
        low = user_prompt.lower()
        if "analyze" in low or "plan" in low:
            if "refund" in low:
                return (
                    "### Cognitive Execution Plan\n"
                    "1. Analyze repository architecture and verify calculate_refund() in refunds.py.\n"
                    "2. Retrieve refund eligibility policy from indexed Knowledge Base (docs/refund_policy.md).\n"
                    "3. Synthesize minimal patch enforcing 30-day cutoff per business rules.\n"
                    "4. Execute isolated verification tests (test_refunds.py) in scratch sandbox.\n"
                    "5. Stage unified diff proposal for explicit human review (Zero Silent Mutation)."
                )
            elif "password" in low or "auth" in low or "token" in low:
                return (
                    "### Cognitive Execution Plan\n"
                    "1. Analyze authentication module structure and security requirements.\n"
                    "2. Retrieve password complexity rules from indexed specifications.\n"
                    "3. Synthesize validation routine enforcing minimum length and character classes.\n"
                    "4. Run isolated regression tests in sandbox environment.\n"
                    "5. Stage unified diff proposal for explicit human review (Zero Silent Mutation)."
                )
            elif "divide" in low or "calc" in low:
                return (
                    "### Cognitive Execution Plan\n"
                    "1. Inspect calculator.py arithmetic routines and AST structure.\n"
                    "2. Retrieve error handling specification from docs/calculator_spec.md.\n"
                    "3. Synthesize divide-by-zero validation patch.\n"
                    "4. Execute isolated unit test suite in scratch sandbox.\n"
                    "5. Stage unified diff proposal for explicit human review (Zero Silent Mutation)."
                )
            else:
                return (
                    "### Cognitive Execution Plan\n"
                    "1. Analyze repository context and requirements for the requested task.\n"
                    "2. Retrieve relevant domain specifications and cited guidelines from indexed Knowledge Base.\n"
                    "3. Formulate minimal unified patch adhering to repository constraints.\n"
                    "4. Execute isolated verification tests in sandboxed scratch space.\n"
                    "5. Stage unified diff for explicit human approval (Zero Silent Mutation)."
                )
        elif "diff" in low or "patch" in low or "fix" in low or "code" in low:
            if "refund" in low:
                return (
                    "```python\n"
                    "def calculate_refund(days_since_purchase: int, amount: float) -> float:\n"
                    "    \"\"\"Calculates refund amount based on 30-day policy.\"\"\"\n"
                    "    if days_since_purchase > 30:\n"
                    "        return 0.0\n"
                    "    return float(amount)\n"
                    "```"
                )
            elif "password" in low or "auth" in low or "token" in low:
                return (
                    "```python\n"
                    "def validate_password(password: str) -> bool:\n"
                    "    \"\"\"Validates password according to security policy (min 8 chars, 1 digit, 1 upper).\"\"\"\n"
                    "    if not password or len(password) < 8:\n"
                    "        return False\n"
                    "    return any(c.isdigit() for c in password) and any(c.isupper() for c in password)\n"
                    "```"
                )
            elif "discount" in low or "price" in low or "tier" in low:
                return (
                    "```python\n"
                    "def calculate_discount(price: float, tier: str) -> float:\n"
                    "    \"\"\"Calculates customer discount according to pricing policy tiers.\"\"\"\n"
                    "    rates = {'gold': 0.20, 'silver': 0.10, 'bronze': 0.05}\n"
                    "    discount_pct = rates.get(tier.lower(), 0.0)\n"
                    "    return round(float(price) * (1.0 - discount_pct), 2)\n"
                    "```"
                )
            elif "divide" in low or "calc" in low or "math" in low:
                if "return 0" in low or "returns 0" in low or "return zero" in low:
                    return (
                        "```python\n"
                        "def divide(a: float, b: float) -> float:\n"
                        "    \"\"\"Divides a by b. Returns 0.0 when dividing by zero.\"\"\"\n"
                        "    if b == 0:\n"
                        "        return 0.0\n"
                        "    return a / b\n"
                        "```"
                    )
                else:
                    return (
                        "```python\n"
                        "def divide(a: float, b: float) -> float:\n"
                        "    \"\"\"Divides a by b with zero check.\"\"\"\n"
                        "    if b == 0:\n"
                        "        raise ValueError('Cannot divide by zero')\n"
                        "    return a / b\n"
                        "```"
                    )
            else:
                return (
                    "```python\n"
                    "def validate_rules(data: dict) -> bool:\n"
                    "    \"\"\"Validates data according to cited specification rules.\"\"\"\n"
                    "    return bool(data)\n"
                    "```"
                )
        elif "critique" in low:
            if "refund" in low:
                return (
                    "### Self-Critique & Boundary Analysis\n"
                    "- Unified diff enforces 30-day refund expiration cutoff as specified.\n"
                    "- Maintains backwards compatibility with valid non-expired transactions.\n"
                    "- Zero side-effects on external dependencies.\n"
                    "- Verified in isolated scratch sandbox (test_refunds.py passed)."
                )
            else:
                return (
                    "### Self-Critique & Boundary Analysis\n"
                    "- Unified diff accurately addresses specified requirements.\n"
                    "- No new dependencies introduced.\n"
                    "- Regression risk: Low.\n"
                    "- Sandbox verification: Pass."
                )
        else:
            return "Task completed successfully according to SentinelForge security policies."

    async def a_generate(self, system_prompt: str, user_prompt: str) -> str:
        return self.generate(system_prompt, user_prompt)


class OllamaProvider(BaseLLMProvider):
    """Provider connecting to local Ollama instance for 100% offline local inference."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    async def a_generate(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]


class GroqProvider(BaseLLMProvider):
    """Zero-cost cloud inference provider using Groq free tier (30 RPM, no credit card)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.groq_api_key or ""
        self.model = model or settings.groq_model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            logger.warning("Groq API key not set. Falling back to MockLLMProvider.")
            return MockLLMProvider().generate(system_prompt, user_prompt)

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def a_generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            return MockLLMProvider().generate(system_prompt, user_prompt)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def get_llm_provider() -> BaseLLMProvider:
    """Factory selecting provider based on configured LLM_PROVIDER setting."""
    prov = settings.llm_provider.lower()
    if prov == "ollama":
        return OllamaProvider()
    elif prov in ("groq", "groq_free"):
        return GroqProvider()
    else:
        return MockLLMProvider()

