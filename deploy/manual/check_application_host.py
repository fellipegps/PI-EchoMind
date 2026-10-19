"""Read-only EC2 checks with allowlisted output; no environment or raw logs."""
import json
from pathlib import Path
import subprocess


def run(*args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, text=True)


def public_event(event):
    if event.get('event') not in {'rag.warmup', 'rag.retrieval', 'rag.ingestion',
                                 'rag.chat', 'document.ingestion', 'rag.generation'}:
        return None
    output = {key: event[key] for key in
              ('event', 'status', 'stage', 'duration_ms', 'error_code') if key in event}
    counts = event.get('counts', {})
    if isinstance(counts, dict):
        allowed = {'persisted_chunks', 'persisted_parents', 'vector_candidates',
                   'current_candidates', 'approved_candidates', 'lexical_candidates',
                   'returned_results', 'retrieved_results'}
        output['counts'] = {key: value for key, value in counts.items()
                            if key in allowed and type(value) is int and value >= 0}
    return output


def inspect_application():
    report = {"containers": []}
    for service in ("backend", "proxy"):
        item = json.loads(run("docker", "inspect", f"echomind-{service}-1"))[0]
        group = Path(f"/sys/fs/cgroup/system.slice/docker-{item['Id']}.scope")
        metrics = {}
        if group.is_dir():
            for field in ("memory.current", "memory.peak", "memory.max"):
                value = (group / field).read_text().strip()
                metrics[field] = int(value) if value.isdigit() else value
            metrics["memory.events"] = dict(
                (key, int(value)) for key, value in
                (line.split() for line in (group / "memory.events").read_text().splitlines())
            )
        report["containers"].append({
            "service": service, "running": item["State"]["Running"],
            "health": item["State"]["Health"]["Status"],
            "oom_killed": item["State"]["OOMKilled"], "restarts": item["RestartCount"],
            "memory_limit_bytes": item["HostConfig"]["Memory"], "cgroup": metrics,
            "cpu_limit": item["HostConfig"]["NanoCpus"] / 1_000_000_000,
        })
    # Only operational events/fields leave this process, never question text,
    # tenant identity, authorization headers or raw provider diagnostics.
    log = subprocess.run(["docker", "logs", "--tail", "500", "echomind-backend-1"],
                         capture_output=True, text=True)
    events = []
    for line in (log.stdout + "\n" + log.stderr).splitlines():
        start = line.find("{")
        if start < 0:
            continue
        try:
            event = json.loads(line[start:])
        except ValueError:
            continue
        allowed = public_event(event)
        if allowed is not None:
            events.append(allowed)
    report["operational_events"] = events[-25:]
    return report


if __name__ == "__main__":
    try:
        print(json.dumps(inspect_application(), indent=2))
    except Exception:
        print("Application host check unavailable; private diagnostics suppressed.")
        raise SystemExit(1) from None
