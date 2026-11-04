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
            return (
                "### Task Plan\n"
                "1. Analyze repository architecture and target files.\n"
                "2. Retrieve relevant context regarding arithmetic functions.\n"
                "3. Formulate minimal bug fix for calculator divide-by-zero check.\n"
                "4. Execute tests inside sandbox to verify solution.\n"
                "5. Present unified diff for human approval."
            )
        elif "diff" in low or "patch" in low or "fix" in low:
            return (
                "```python\n"
                "def divide(a: float, b: float) -> float:\n"
                "    \"\"\"Divides a by b with zero check.\"\"\"\n"
                "    if b == 0:\n"
                "        raise ValueError('Cannot divide by zero')\n"
                "    return a / b\n"
                "```"
            )
        elif "critique" in low:
            return (
                "### Self-Critique\n"
                "- Unified diff accurately addresses zero division edge case.\n"
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

