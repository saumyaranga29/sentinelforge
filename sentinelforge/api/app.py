import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from sentinelforge.api.middleware import RequestContextMiddleware
from sentinelforge.api.routes_rag import router as rag_router
from sentinelforge.api.routes_mcp import router as mcp_router
from sentinelforge.api.routes_agent import router as agent_router
from sentinelforge.config import settings
from sentinelforge.rag.vector_store import vector_store
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger, setup_logging

logger = get_logger("sentinelforge.api.app")


def bootstrap_sample_data() -> None:
    """
    Bootstraps safe sample repository and documentation on startup.
    Ensures zero-cost deployed demo functions immediately without pre-existing disk state.
    """
    settings.workspace_root.mkdir(parents=True, exist_ok=True)

    sample_calc = settings.workspace_root / "calculator.py"
    if not sample_calc.exists():
        sample_calc.write_text(
            '"""Simple Calculator Module for SentinelForge Demo."""\n\n'
            "def add(a: float, b: float) -> float:\n"
            "    return a + b\n\n"
            "def subtract(a: float, b: float) -> float:\n"
            "    return a - b\n\n"
            "def multiply(a: float, b: float) -> float:\n"
            "    return a * b\n\n"
            "def divide(a: float, b: float) -> float:\n"
            "    if b == 0:\n"
            "        raise ValueError('Cannot divide by zero')\n"
            "    return a / b\n",
            encoding="utf-8",
        )

    sample_test = settings.workspace_root / "test_calculator.py"
    if not sample_test.exists():
        sample_test.write_text(
            "import unittest\n"
            "from calculator import add, subtract, multiply, divide\n\n"
            "class TestCalculator(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n\n"
            "    def test_subtract(self):\n"
            "        self.assertEqual(subtract(5, 2), 3)\n\n"
            "    def test_multiply(self):\n"
            "        self.assertEqual(multiply(3, 4), 12)\n\n"
            "    def test_divide(self):\n"
            "        self.assertEqual(divide(10, 2), 5)\n\n"
            "    def test_divide_by_zero(self):\n"
            "        with self.assertRaises(ValueError):\n"
            "            divide(10, 0)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )

    docs_dir = settings.workspace_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    sample_doc = docs_dir / "calculator_spec.md"
    if not sample_doc.exists():
        sample_doc.write_text(
            "# Calculator Specification\n\n"
            "## Architecture\n"
            "The calculator module provides basic arithmetic operations: add, subtract, multiply, divide.\n\n"
            "## Error Handling\n"
            "Division by zero is strictly prohibited and must raise a ValueError with the message 'Cannot divide by zero'.\n\n"
            "## Testing Strategy\n"
            "All arithmetic operations are verified using standard Python unittest fixtures.\n",
            encoding="utf-8",
        )

    sample_refund = settings.workspace_root / "refunds.py"
    if not sample_refund.exists():
        sample_refund.write_text(
            '"""Refund Processing Service."""\n\n'
            "def calculate_refund(days_since_purchase: int, amount: float) -> float:\n"
            '    """Calculates refund amount based on purchase date and company policy."""\n'
            "    # Legacy behavior: returns full refund without cutoff check\n"
            "    return float(amount)\n",
            encoding="utf-8",
        )

    sample_refund_test = settings.workspace_root / "test_refunds.py"
    if not sample_refund_test.exists():
        sample_refund_test.write_text(
            "import unittest\n"
            "from refunds import calculate_refund\n\n"
            "class TestRefundPolicy(unittest.TestCase):\n"
            "    def test_recent_purchase_refund(self):\n"
            "        self.assertEqual(calculate_refund(10, 150.0), 150.0)\n\n"
            "    def test_reject_refund_older_than_30_days(self):\n"
            "        self.assertEqual(calculate_refund(35, 150.0), 0.0)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )

    sample_policy_doc = docs_dir / "refund_policy.md"
    if not sample_policy_doc.exists():
        sample_policy_doc.write_text(
            "# Enterprise Refund Policy Specification\n\n"
            "## Scope & Terms\n"
            "This policy governs all consumer transaction refund calculations across services.\n\n"
            "## Eligibility Expiration Rule\n"
            "Refund requests must be initiated within thirty (30) calendar days of purchase.\n"
            "Any refund requested after 30 days must be strictly rejected with an approved amount of 0.0.\n\n"
            "## Verification\n"
            "All refund logic must be verified by automated regression test suites.\n",
            encoding="utf-8",
        )

    try:
        vector_store.ingest_file(sample_calc)
        vector_store.ingest_file(sample_doc)
        vector_store.ingest_file(sample_refund)
        vector_store.ingest_file(sample_policy_doc)
        logger.info("Successfully bootstrapped and indexed sample repository and documents.")
    except Exception as e:
        logger.warning(f"Error indexing sample documents during bootstrap: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    setup_logging(level="DEBUG" if settings.debug else "INFO")
    logger.info("Initializing SentinelForge Backend Platform...")
    bootstrap_sample_data()
    yield
    logger.info("Shutting down SentinelForge Backend Platform...")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="SentinelForge API",
        description=(
            "Privacy-first AI developer platform integrating MCP, local RAG, "
            "and sandboxed code-generation agent."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(rag_router)
    app.include_router(mcp_router)
    app.include_router(agent_router)

    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        """Serves the SentinelForge Single Page Application dashboard."""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(
                index_file,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        return {"message": "SentinelForge API is running. UI not found."}

    @app.get("/health", tags=["Health"])
    async def health_check():
        """System health and operational status endpoint."""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "mode": settings.app_mode,
            "is_local_processing": settings.llm_provider != "groq_free",
            "llm_provider": settings.llm_provider,
            "rag_chunks_indexed": vector_store.get_stats().get("total_chunks", 0),
        }

    @app.get("/api/audit/logs", tags=["Audit & Telemetry"])
    async def get_audit_logs(limit: int = 50):
        """Retrieves structured sandbox and agent audit events (Bonus Telemetry)."""
        events = audit_logger.get_recent_events(limit=limit)
        return {"total": len(events), "events": [e.model_dump() for e in events]}

    return app


app = create_app()

