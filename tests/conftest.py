import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from sentinelforge.api.app import app
from sentinelforge.config import settings
from sentinelforge.sandbox.runner import SandboxRunner
from sentinelforge.rag.vector_store import LocalVectorStore
from sentinelforge.agent.diff_engine import DiffEngine


@pytest.fixture
def temp_workspace():
    """Provides an isolated temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        original_ws = settings.workspace_root
        settings.workspace_root = tmp_path

        # Create sample files
        calc_file = tmp_path / "calculator.py"
        calc_file.write_text(
            "def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b\n",
            encoding="utf-8",
        )

        test_file = tmp_path / "test_calculator.py"
        test_file.write_text(
            "import unittest\nfrom calculator import add, divide\n\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 2), 4)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n",
            encoding="utf-8",
        )

        yield tmp_path
        settings.workspace_root = original_ws


@pytest.fixture
def sandbox(temp_workspace):
    """Provides a configured SandboxRunner bound to temp_workspace."""
    return SandboxRunner(workspace_root=temp_workspace)


@pytest.fixture
def test_vector_store(temp_workspace):
    """Provides an isolated vector store for testing."""
    store_dir = temp_workspace / "chroma_test"
    return LocalVectorStore(persist_dir=store_dir)


@pytest.fixture
def test_diff_engine(temp_workspace):
    """Provides an isolated DiffEngine bound to temp_workspace."""
    return DiffEngine(workspace_root=temp_workspace)


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)

