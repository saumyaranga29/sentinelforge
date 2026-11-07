import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sentinelforge.config import settings
from sentinelforge.rag.embeddings import LocalEmbeddingEngine
from sentinelforge.rag.injection_guard import PromptInjectionGuard, InjectionScanResult
from sentinelforge.rag.parsers import DocumentChunk, get_parser_for_file
from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.rag.vector_store")

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None


class Citation(BaseModel):
    """Citation metadata for retrieved evidence."""

    source_file: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    similarity_score: float = 0.0
    citation_text: str
    encapsulated_text: str
    injection_flagged: bool = False


class LocalVectorStore:
    """
    Manages local vector indexing, deduplication, incremental updates, and citation retrieval.
    Guarantees 100% local operation with zero external cloud dependencies.
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = (persist_dir or settings.chroma_persist_dir).resolve()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedder = LocalEmbeddingEngine()

        self._hash_registry_file = self.persist_dir / "hash_registry.json"
        self._hash_registry: Dict[str, str] = self._load_hash_registry()

        self._client = None
        self._collection = None
        self._in_memory_docs: List[DocumentChunk] = []
        self._in_memory_vectors: List[List[float]] = []

        self._init_store()

    def _load_hash_registry(self) -> Dict[str, str]:
        if self._hash_registry_file.exists():
            try:
                with open(self._hash_registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading hash registry: {e}")
        return {}

    def _save_hash_registry(self) -> None:
        try:
            with open(self._hash_registry_file, "w", encoding="utf-8") as f:
                json.dump(self._hash_registry, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save hash registry: {e}")

    def _init_store(self) -> None:
        if chromadb is not None:
            try:
                chroma_settings = ChromaSettings(anonymized_telemetry=False) if ChromaSettings else None
                self._client = (
                    chromadb.PersistentClient(path=str(self.persist_dir), settings=chroma_settings)
                    if chroma_settings
                    else chromadb.PersistentClient(path=str(self.persist_dir))
                )
                self._collection = self._client.get_or_create_collection(
                    name="sentinelforge_rag",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"Initialized ChromaDB vector store at {self.persist_dir}")
                return
            except Exception as e:
                logger.warning(f"ChromaDB initialization failed: {e}. Using resilient in-memory index.")

        logger.info("Operating in-memory vector storage mode.")

    def ingest_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parses, checks hashes for duplicate detection, embeds, and indexes a file.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        if self._hash_registry.get(str(file_path)) == file_hash:
            logger.info(f"Duplicate file detected: {file_path.name}. Skipping redundant re-indexing.")
            return {
                "status": "skipped",
                "reason": "duplicate_content_hash",
                "file": file_path.name,
                "file_hash": file_hash,
                "chunks_indexed": 0,
            }

        self.delete_by_source(file_path.name)

        parser = get_parser_for_file(file_path)
        chunks = parser.parse(file_path)

        if not chunks:
            return {"status": "empty", "file": file_path.name, "chunks_indexed": 0}

        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed_texts(texts)

        if self._collection is not None:
            ids = [c.chunk_id for c in chunks]
            metadatas = [
                {
                    "source_file": c.source_file,
                    "source_type": c.source_type,
                    "content_hash": c.content_hash,
                    "page_number": c.page_number or -1,
                    "section": c.section or "",
                    "line_start": c.line_start or -1,
                    "line_end": c.line_end or -1,
                }
                for c in chunks
            ]
            self._collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        else:
            self._in_memory_docs.extend(chunks)
            self._in_memory_vectors.extend(embeddings)

        self._hash_registry[str(file_path)] = file_hash
        self._save_hash_registry()

        audit_logger.record_event(
            event_type="RAG_CONTENT_INGESTED",
            target_path=str(file_path),
            details={"chunks_count": len(chunks), "file_hash": file_hash},
            success=True,
        )

        return {
            "status": "indexed",
            "file": file_path.name,
            "file_hash": file_hash,
            "chunks_indexed": len(chunks),
        }

    def delete_by_source(self, source_file: str) -> int:
        """Deletes all chunks belonging to a specific source file."""
        deleted_count = 0
        if self._collection is not None:
            try:
                results = self._collection.get(where={"source_file": source_file})
                if results and results.get("ids"):
                    self._collection.delete(ids=results["ids"])
                    deleted_count = len(results["ids"])
            except Exception as e:
                logger.error(f"Error deleting from ChromaDB: {e}")
        else:
            new_docs = []
            new_vecs = []
            for doc, vec in zip(self._in_memory_docs, self._in_memory_vectors):
                if doc.source_file != source_file:
                    new_docs.append(doc)
                    new_vecs.append(vec)
                else:
                    deleted_count += 1
            self._in_memory_docs = new_docs
            self._in_memory_vectors = new_vecs

        for key in list(self._hash_registry.keys()):
            if Path(key).name == source_file:
                del self._hash_registry[key]
        self._save_hash_registry()

        if deleted_count > 0:
            audit_logger.record_event(
                event_type="RAG_CONTENT_DELETED",
                target_path=source_file,
                details={"deleted_chunks": deleted_count},
                success=True,
            )

        return deleted_count

    def retrieve(self, query: str, top_k: int = 5) -> List[Citation]:
        """
        Retrieves top_k context chunks for a query, preserving citations and applying injection defense.
        """
        if not query.strip():
            return []

        query_vec = self.embedder.embed_query(query)
        citations: List[Citation] = []

        if self._collection is not None and self._collection.count() > 0:
            results = self._collection.query(
                query_embeddings=[query_vec],
                n_results=min(top_k, self._collection.count()),
            )

            if results and results.get("documents") and results["documents"][0]:
                for i, doc_text in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0.5
                    similarity = max(0.0, 1.0 - distance)

                    source_file = meta.get("source_file", "unknown")
                    page_num = meta.get("page_number") if meta.get("page_number", -1) != -1 else None
                    l_start = meta.get("line_start") if meta.get("line_start", -1) != -1 else None
                    l_end = meta.get("line_end") if meta.get("line_end", -1) != -1 else None

                    ref_parts = [source_file]
                    if page_num:
                        ref_parts.append(f"page {page_num}")
                    elif l_start and l_end:
                        ref_parts.append(f"lines {l_start}-{l_end}")
                    citation_ref = ", ".join(ref_parts)

                    encapsulated, scan = PromptInjectionGuard.encapsulate_chunk(
                        text=doc_text,
                        source_file=source_file,
                        citation_ref=citation_ref,
                    )

                    citations.append(
                        Citation(
                            source_file=source_file,
                            page_number=page_num,
                            section=meta.get("section") or None,
                            line_start=l_start,
                            line_end=l_end,
                            similarity_score=round(similarity, 4),
                            citation_text=citation_ref,
                            encapsulated_text=encapsulated,
                            injection_flagged=scan.is_suspicious,
                        )
                    )
        elif self._in_memory_docs:
            import numpy as np

            q_arr = np.array(query_vec, dtype=np.float32)
            scores = []
            for vec in self._in_memory_vectors:
                v_arr = np.array(vec, dtype=np.float32)
                sim = float(np.dot(q_arr, v_arr) / (np.linalg.norm(q_arr) * np.linalg.norm(v_arr) + 1e-9))
                scores.append(sim)

            top_indices = np.argsort(scores)[::-1][:top_k]
            for idx in top_indices:
                doc = self._in_memory_docs[idx]
                sim = scores[idx]

                ref_parts = [doc.source_file]
                if doc.page_number:
                    ref_parts.append(f"page {doc.page_number}")
                elif doc.line_start and doc.line_end:
                    ref_parts.append(f"lines {doc.line_start}-{doc.line_end}")
                citation_ref = ", ".join(ref_parts)

                encapsulated, scan = PromptInjectionGuard.encapsulate_chunk(
                    text=doc.content,
                    source_file=doc.source_file,
                    citation_ref=citation_ref,
                )

                citations.append(
                    Citation(
                        source_file=doc.source_file,
                        page_number=doc.page_number,
                        section=doc.section,
                        line_start=doc.line_start,
                        line_end=doc.line_end,
                        similarity_score=round(sim, 4),
                        citation_text=citation_ref,
                        encapsulated_text=encapsulated,
                        injection_flagged=scan.is_suspicious,
                    )
                )

        return citations

    def get_stats(self) -> Dict[str, Any]:
        """Returns indexed document statistics."""
        count = self._collection.count() if self._collection is not None else len(self._in_memory_docs)
        files_summary = []
        for file_path_str, fhash in self._hash_registry.items():
            p = Path(file_path_str)
            files_summary.append({
                "name": p.name,
                "path": str(p),
                "hash": fhash[:8] if fhash else "indexed",
            })
        return {
            "total_chunks": count,
            "indexed_files": list(self._hash_registry.keys()),
            "files": files_summary,
            "storage_path": str(self.persist_dir),
            "engine": "ChromaDB" if self._collection is not None else "InMemoryFallback",
        }


vector_store = LocalVectorStore()

