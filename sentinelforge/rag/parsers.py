import hashlib
import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

try:
    import pypdf
except ImportError:
    pypdf = None


class DocumentChunk(BaseModel):
    """Normalized document chunk carrying complete citation metadata."""

    chunk_id: str
    content: str
    source_file: str
    source_type: str
    content_hash: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class BaseDocumentParser:
    """Base parser defining the extraction interface."""

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        raise NotImplementedError


class PDFDocumentParser(BaseDocumentParser):
    """Extracts text per page from PDF files, preserving page metadata."""

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        if pypdf is None:
            return chunks

        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page_idx, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text() or ""
                    except Exception:
                        text = ""
                    text = text.strip()
                    if not text:
                        continue

                    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    chunk_id = f"{file_path.name}_p{page_idx + 1}_{content_hash[:8]}"

                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            content=text,
                            source_file=file_path.name,
                            source_type="pdf",
                            content_hash=content_hash,
                            page_number=page_idx + 1,
                        )
                    )
        except Exception:
            pass
        return chunks


class MarkdownDocumentParser(BaseDocumentParser):
    """Extracts sections from markdown documents, preserving section headers and line numbers."""

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        current_section = "Introduction"
        current_lines: List[str] = []
        section_start_line = 1

        for idx, line in enumerate(lines, start=1):
            if line.startswith("#"):
                if current_lines:
                    text = "".join(current_lines).strip()
                    if text:
                        c_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                        chunks.append(
                            DocumentChunk(
                                chunk_id=f"{file_path.name}_l{section_start_line}_{c_hash[:8]}",
                                content=text,
                                source_file=file_path.name,
                                source_type="markdown",
                                content_hash=c_hash,
                                section=current_section,
                                line_start=section_start_line,
                                line_end=idx - 1,
                            )
                        )
                current_section = line.strip("#").strip()
                current_lines = [line]
                section_start_line = idx
            else:
                current_lines.append(line)

        if current_lines:
            text = "".join(current_lines).strip()
            if text:
                c_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{file_path.name}_l{section_start_line}_{c_hash[:8]}",
                        content=text,
                        source_file=file_path.name,
                        source_type="markdown",
                        content_hash=c_hash,
                        section=current_section,
                        line_start=section_start_line,
                        line_end=len(lines),
                    )
                )

        return chunks


class CodeDocumentParser(BaseDocumentParser):
    """Extracts code blocks preserving exact line ranges for Python, JS, and TS."""

    def __init__(self, window_lines: int = 40, overlap_lines: int = 10):
        self.window_lines = window_lines
        self.overlap_lines = overlap_lines

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if total_lines == 0:
            return chunks

        ext = file_path.suffix.lower()
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript"}
        source_type = lang_map.get(ext, "code")

        start = 0
        while start < total_lines:
            end = min(start + self.window_lines, total_lines)
            chunk_slice = lines[start:end]
            text = "".join(chunk_slice).strip()

            if text:
                c_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{file_path.name}_l{start + 1}-{end}_{c_hash[:8]}",
                        content=text,
                        source_file=file_path.name,
                        source_type=source_type,
                        content_hash=c_hash,
                        line_start=start + 1,
                        line_end=end,
                    )
                )

            if end == total_lines:
                break
            start += max(1, self.window_lines - self.overlap_lines)

        return chunks


class JSONDocumentParser(BaseDocumentParser):
    """Parses JSON files into readable structured chunks."""

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        text = json.dumps(data, indent=2)
        c_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return [
            DocumentChunk(
                chunk_id=f"{file_path.name}_{c_hash[:8]}",
                content=text,
                source_file=file_path.name,
                source_type="json",
                content_hash=c_hash,
                line_start=1,
                line_end=len(text.splitlines()),
            )
        ]


class TextDocumentParser(BaseDocumentParser):
    """Generic text fallback parser."""

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().strip()

        if not text:
            return []

        c_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return [
            DocumentChunk(
                chunk_id=f"{file_path.name}_{c_hash[:8]}",
                content=text,
                source_file=file_path.name,
                source_type="text",
                content_hash=c_hash,
                line_start=1,
                line_end=len(text.splitlines()),
            )
        ]


def get_parser_for_file(file_path: Path) -> BaseDocumentParser:
    """Factory selecting the appropriate parser based on file extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return PDFDocumentParser()
    elif suffix in (".md", ".markdown"):
        return MarkdownDocumentParser()
    elif suffix in (".py", ".js", ".ts"):
        return CodeDocumentParser()
    elif suffix == ".json":
        return JSONDocumentParser()
    else:
        return TextDocumentParser()

