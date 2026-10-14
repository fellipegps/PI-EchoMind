"""Synthetic E5 workload in the production image. No real credentials or services.

Uses the app's actual singleton, prefixes, extraction/chunking and one-at-a-time
document embedding. Reports cgroup v2 memory (including page cache), RSS, CPU
and timings. External LLM/DB/auth calls are deliberately excluded.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

sys.path.insert(0, '/app')

CGROUP = Path('/sys/fs/cgroup')
START = time.monotonic()


def metric(name, **extra):
    status = Path('/proc/self/status').read_text()
    rss_kib = int(next(line for line in status.splitlines() if line.startswith('VmRSS:')).split()[1])
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    values = {'phase': name, 'elapsed_seconds': round(time.monotonic() - START, 3),
              'rss_mib': round(rss_kib / 1024, 2),
              'max_rss_mib': round(cpu.ru_maxrss / 1024, 2),
              'cpu_seconds': round(cpu.ru_utime + cpu.ru_stime, 3)}
    for filename in ('memory.current', 'memory.peak', 'memory.max'):
        value = (CGROUP / filename).read_text().strip()
        values[filename.replace('.', '_') + '_mib'] = round(int(value) / 1024**2, 2) if value != 'max' else value
    values['memory_events'] = dict(line.split() for line in (CGROUP / 'memory.events').read_text().splitlines())
    print(json.dumps(values | extra), flush=True)


metric('python')
from app import main  # Full application import footprint, without lifespan/provider calls.
from app.document_ingestion import chunk_document, extract_txt, group_document_children
from app.rag_engine import _get_embeddings
metric('application_imported')
embedding = _get_embeddings()
metric('model_loaded', model='intfloat/multilingual-e5-small', batch_size=embedding.batch_size,
       parallel=embedding.parallel)
query = 'Como fazer matrícula e consultar os horários das aulas?'
assert len(embedding.embed_query(query)) == 384
metric('first_query')

# A large plain-text upload exercises extraction + chunk/parent allocation.
# Only a representative subset is encoded, exactly one chunk per call as in PGVector.
paragraph = ('Regulamento acadêmico. A matrícula exige documento de identidade, histórico escolar '
             'e formulário preenchido. O atendimento ocorre de segunda a sexta-feira. '
             'As disciplinas e os horários podem ser consultados na secretaria acadêmica.\n\n')
content = (paragraph.encode() * (10 * 1024**2 // len(paragraph.encode()) + 1))[:10 * 1024**2]
# Keep valid UTF-8 at the maximum byte boundary, without artificially changing extractor behavior.
content = content.decode('utf-8', errors='ignore').encode()
extracted = extract_txt(content)
chunks = chunk_document(extracted)
grouped = group_document_children(chunks)
metric('max_txt_chunked', upload_bytes=len(content), chunks=len(chunks), parents=len(grouped.parents))

def document_workload():
    for chunk in chunks[:40]:
        vectors = embedding.embed_documents([chunk.content])
        assert len(vectors) == 1 and len(vectors[0]) == 384

def query_workload():
    for _ in range(20):
        assert len(embedding.embed_query(query)) == 384

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(document_workload), executor.submit(query_workload)]
    for future in futures:
        future.result()
metric('ingestion_and_chat_overlap', encoded_document_chunks=40, encoded_chat_queries=20)

hashes = []
for path in sorted(Path('/var/cache/echomind/models').rglob('*.onnx')):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    hashes.append({'file': path.name, 'sha256': digest.hexdigest(), 'bytes': path.stat().st_size})
metric('completed', onnx_files=hashes)
