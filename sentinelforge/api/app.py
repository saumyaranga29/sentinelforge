import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    # 1. Sample Python Code
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

    # 2. Sample Unit Tests
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

    # 3. Sample Specification Document
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

    # Automatically index sample docs and code into local RAG
    try:
        vector_store.ingest_file(sample_calc)
        vector_store.ingest_file(sample_doc)
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

    # Middleware
    # app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(rag_router)
    app.include_router(mcp_router)
    app.include_router(agent_router)

    # Root & Health Endpoints
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

