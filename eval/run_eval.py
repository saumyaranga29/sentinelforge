import json
import time
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinelforge.config import settings
from sentinelforge.rag.vector_store import vector_store


def run_benchmark(benchmark_file: Path) -> Dict[str, Any]:
    """Runs the in-repo retrieval evaluation benchmark suite."""
    with open(benchmark_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # Ingest sample documents into vector store
    sample_files = [
        settings.workspace_root / "calculator.py",
        settings.workspace_root / "docs" / "calculator_spec.md",
        settings.workspace_root / "test_calculator.py",
    ]
    for sf in sample_files:
        if sf.exists():
            vector_store.ingest_file(sf)

    total_queries = len(cases)
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks: List[float] = []
    latencies_ms: List[float] = []
    failures: List[Dict[str, Any]] = []

    print("\n" + "=" * 70)
    print(" SentinelForge Retrieval Evaluation Benchmark Suite")
    print("=" * 70)

    for item in cases:
        q_id = item["id"]
        query = item["query"]
        expected_src = item["expected_source"].lower()

        t0 = time.perf_counter()
        citations = vector_store.retrieve(query=query, top_k=5)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        latencies_ms.append(elapsed_ms)

        retrieved_sources = [c.source_file.lower() for c in citations]

        hit_rank = None
        for rank, src in enumerate(retrieved_sources, start=1):
            if expected_src in src:
                hit_rank = rank
                break

        if hit_rank == 1:
            hits_at_1 += 1
        if hit_rank and hit_rank <= 3:
            hits_at_3 += 1
        if hit_rank and hit_rank <= 5:
            hits_at_5 += 1

        if hit_rank:
            reciprocal_ranks.append(1.0 / hit_rank)
        else:
            reciprocal_ranks.append(0.0)
            failures.append({
                "query_id": q_id,
                "query": query,
                "expected": expected_src,
                "retrieved": retrieved_sources,
                "reason": "SOURCE_NOT_FOUND_IN_TOP_5",
            })

        status_str = f"HIT (Rank {hit_rank})" if hit_rank else "MISS"
        print(f"[{q_id}] {status_str:<12} {elapsed_ms:>6.2f}ms | Query: {query[:50]}")

    mrr = sum(reciprocal_ranks) / total_queries if total_queries > 0 else 0.0
    avg_latency = sum(latencies_ms) / total_queries if total_queries > 0 else 0.0

    metrics = {
        "total_queries": total_queries,
        "hit_at_1": hits_at_1 / total_queries,
        "hit_at_3": hits_at_3 / total_queries,
        "hit_at_5": hits_at_5 / total_queries,
        "mrr": round(mrr, 4),
        "avg_latency_ms": round(avg_latency, 2),
        "failure_count": len(failures),
        "failures": failures,
    }

    print("-" * 70)
    print(f"Results Summary:")
    print(f"  Hit@1:  {metrics['hit_at_1'] * 100:.1f}%")
    print(f"  Hit@3:  {metrics['hit_at_3'] * 100:.1f}%")
    print(f"  Hit@5:  {metrics['hit_at_5'] * 100:.1f}%")
    print(f"  MRR:    {metrics['mrr']:.4f}")
    print(f"  Avg Latency: {metrics['avg_latency_ms']} ms")
    print("=" * 70 + "\n")

    return metrics


if __name__ == "__main__":
    benchmark_path = Path(__file__).parent / "benchmark_data.json"
    run_benchmark(benchmark_path)

