"""Compare legacy per-chunk writes and batches on disposable local pgvector only.

Synthetic vectors isolate database work by default; --real-embeddings also tests
the cached E5 model. No runtime dotenv, remote database, Groq or user content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(chunks_count: int, repeats: int, real_embeddings: bool, statement_delay_ms: float,
        model_path: Path | None = None):
    url = make_url(os.environ["DATABASE_URL"])
    if (url.get_backend_name() != "postgresql" or url.database != "echomind_integration"
            or url.host not in {"localhost", "127.0.0.1", "::1", "echomind-batch-regression"}):
        raise ValueError("Only the explicitly disposable local integration database is accepted.")
    os.environ["ECHOMIND_ENV"] = "testing"
    from langchain_core.embeddings import Embeddings
    from app import rag_engine as rag

    class SyntheticEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return [self.embed_query(value) for value in texts]

        def embed_query(self, value):
            digest = hashlib.sha256(value.encode()).digest()
            return [(digest[i % 32] - 127.5) / 127.5 for i in range(384)]

    if not real_embeddings:
        rag._get_embeddings = lambda: SyntheticEmbeddings()
    elif model_path is not None:
        # Benchmark-only cache selection. The production adapter and inference
        # settings stay unchanged; the constructor cannot try a network download.
        import fastembed
        original_encoder = fastembed.TextEmbedding
        class CachedTextEmbedding(original_encoder):
            def __init__(self, **kwargs):
                super().__init__(specific_model_path=str(model_path), local_files_only=True, **kwargs)
        fastembed.TextEmbedding = CachedTextEmbedding
    samples = []
    token = uuid4().hex
    tenant = "benchmark-" + token
    store = rag._get_vector_store(tenant)
    indexer = object.__new__(rag.RAGEngine)
    indexer.tenant_id = tenant
    document = SimpleNamespace(
        id=token, tenant_id=tenant, filename="synthetic.txt", mime_type="text/plain",
        document_type=None, document_number=None, department=None, published_at=None, valid_until=None,
    )
    chunks = [SimpleNamespace(
        id=f"{token}-{i}", tenant_id=tenant, document_id=token, chunk_index=i,
        content=(f"Secao sintetica {i}. Prazo de resposta de trinta dias. " * 8),
        page_start=None, page_end=None, section_title=None, parent_id=None,
    ) for i in range(chunks_count)]
    # Warm inference/collection before either timed path, using the same singleton.
    assert len(store.embedding_function.embed_documents([chunks[0].content])[0]) == 384
    counters = {}
    def statement(_conn, _cursor, statement, *_args):
        counters["statements"] += 1
        if statement.lstrip().upper().startswith("INSERT INTO LANGCHAIN_PG_EMBEDDING"):
            counters["insert_statements"] += 1
        if statement_delay_ms:
            time.sleep(statement_delay_ms / 1000)
    def committed(_session):
        counters["commits"] += 1
    try:
        for repeat in range(repeats):
            # Alternate order so a warmer connection does not always favor batching.
            modes = ("legacy", "batch32") if repeat % 2 == 0 else ("batch32", "legacy")
            for mode in modes:
                store.delete(ids=[rag._make_vector_id(c.id, "document_chunk", tenant) for c in chunks], collection_only=True)
                counters = {"statements": 0, "insert_statements": 0, "commits": 0}
                event.listen(store._bind, "before_cursor_execute", statement)
                event.listen(Session, "after_commit", committed)
                started = time.perf_counter()
                try:
                    if mode == "legacy":
                        indexer._delete_vector_ids([rag._make_vector_id(c.id, "document_chunk", tenant) for c in chunks])
                        for chunk in chunks:
                            indexer._index_document_chunk(document, chunk)
                    else:
                        indexer.reindex_document_chunks(document, chunks)
                finally:
                    elapsed = time.perf_counter() - started
                    event.remove(store._bind, "before_cursor_execute", statement)
                    event.remove(Session, "after_commit", committed)
                with store._bind.connect() as connection:
                    count = connection.execute(text(
                        "SELECT count(*) FROM langchain_pg_embedding e JOIN langchain_pg_collection c "
                        "ON c.uuid=e.collection_id WHERE c.name=:name"
                    ), {"name": rag._tenant_collection_name(tenant)}).scalar_one()
                assert count == chunks_count
                samples.append({"mode": mode, "repeat": repeat + 1, "seconds": round(elapsed, 4),
                                "vectors_verified": count, **counters})
        times = {mode: statistics.median(s["seconds"] for s in samples if s["mode"] == mode)
                 for mode in ("legacy", "batch32")}
        memory = {}
        for name in ("memory.peak", "memory.max", "memory.events"):
            path = Path('/sys/fs/cgroup') / name
            if path.exists():
                memory[name] = path.read_text().strip()
        return {"chunks": chunks_count, "repeats": repeats, "batch_size": 32,
                "embedding_batch_size": 1, "real_e5": real_embeddings,
                "explicit_cached_model": model_path is not None,
                "simulated_delay_per_sql_statement_ms": statement_delay_ms,
                "median_seconds": times, "speedup": round(times["legacy"] / times["batch32"], 2),
                "samples": samples, "cgroup": memory,
                "scope": "Disposable local pgvector, synthetic text; not production latency, upload or sustained load."}
    finally:
        store.delete_collection()
        rag._get_vector_store.cache_clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=int, choices=(65, 104, 335), default=335)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--real-embeddings", action="store_true")
    parser.add_argument("--model-path", type=Path, help="Cached model snapshot directory, for offline real E5 only")
    parser.add_argument("--statement-delay-ms", type=float, choices=(0, 25, 50), default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.model_path and not args.real_embeddings:
        parser.error("--model-path requires --real-embeddings")
    result = run(args.chunks, args.repeats, args.real_embeddings, args.statement_delay_ms, args.model_path)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
