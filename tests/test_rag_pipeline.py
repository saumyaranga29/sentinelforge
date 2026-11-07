from pathlib import Path
from sentinelforge.rag.parsers import MarkdownDocumentParser, CodeDocumentParser
from sentinelforge.rag.vector_store import LocalVectorStore


def test_markdown_parser_sections(temp_workspace):
    """Verifies that Markdown parser extracts headers as sections with line numbers."""
    md_file = temp_workspace / "guide.md"
    md_file.write_text(
        "# Title\nIntro text.\n\n## Section One\nDetailed explanations.\n\n## Section Two\nClosing notes.\n",
        encoding="utf-8",
    )

    parser = MarkdownDocumentParser()
    chunks = parser.parse(md_file)

    assert len(chunks) >= 2
    sections = [c.section for c in chunks]
    assert "Section One" in sections
    assert chunks[0].line_start is not None
    assert chunks[0].line_end is not None


def test_code_parser_line_ranges(temp_workspace):
    """Verifies that Code parser segments python files while preserving line ranges."""
    py_file = temp_workspace / "logic.py"
    py_lines = [f"def func_{i}():\n    return {i}\n" for i in range(25)]
    py_file.write_text("\n".join(py_lines), encoding="utf-8")

    parser = CodeDocumentParser(window_lines=15, overlap_lines=5)
    chunks = parser.parse(py_file)

    assert len(chunks) > 1
    assert chunks[0].source_type == "python"
    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 15


def test_duplicate_content_deduplication(test_vector_store, temp_workspace):
    """Verifies that ingesting the identical file twice skips redundant processing."""
    file_path = temp_workspace / "doc.txt"
    file_path.write_text("Unique invariant text for deduplication verification.", encoding="utf-8")

    res1 = test_vector_store.ingest_file(file_path)
    assert res1["status"] == "indexed"
    assert res1["chunks_indexed"] > 0

    res2 = test_vector_store.ingest_file(file_path)
    assert res2["status"] == "skipped"
    assert res2["reason"] == "duplicate_content_hash"


def test_deletion_of_indexed_content(test_vector_store, temp_workspace):
    """Verifies that chunks for a specific file can be cleanly deleted."""
    file_path = temp_workspace / "temp_doc.txt"
    file_path.write_text("Temporary information to be removed.", encoding="utf-8")

    test_vector_store.ingest_file(file_path)
    citations_before = test_vector_store.retrieve(query="Temporary information", top_k=5)
    assert len(citations_before) > 0

    deleted_count = test_vector_store.delete_by_source("temp_doc.txt")
    assert deleted_count > 0

    citations_after = test_vector_store.retrieve(query="Temporary information", top_k=5)
    matching_after = [c for c in citations_after if c.source_file == "temp_doc.txt"]
    assert len(matching_after) == 0


def test_retrieval_citations(test_vector_store, temp_workspace):
    """Verifies that retrieved context includes exact citations and confidence scores."""
    spec_file = temp_workspace / "spec.md"
    spec_file.write_text(
        "# Architecture\nThe platform uses FastMCP protocol for all tool communications.\n",
        encoding="utf-8",
    )
    test_vector_store.ingest_file(spec_file)

    citations = test_vector_store.retrieve(query="What protocol is used for tool communication?", top_k=2)
    assert len(citations) > 0
    top_citation = citations[0]
    assert top_citation.source_file == "spec.md"
    assert top_citation.similarity_score > 0.0
    assert "FastMCP" in top_citation.encapsulated_text

