"""Observe the existing EC2 containers without reading credentials or user data.

Run on the host. Output contains counters only. No load is generated here.
Use --stop-file to finish early after a bounded, separately controlled workload.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time


def read_pairs(path):
    return {key: int(value) for key, value in
            (line.split() for line in path.read_text().splitlines())}


def sample():
    memory = {line.split(':', 1)[0]: int(line.split()[1]) * 1024
              for line in Path('/proc/meminfo').read_text().splitlines()}
    cpu = [int(value) for value in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
    # guest counters are already included in user/nice and must not be summed twice.
    values = {'at': datetime.now(timezone.utc).isoformat(),
              'monotonic': time.monotonic(), 'host_cpu_total': sum(cpu[:8]),
              'host_cpu_idle': cpu[3] + cpu[4],
              'host_memory_total_bytes': memory['MemTotal'],
              'host_memory_available_bytes': memory['MemAvailable'],
              'host_swap_total_bytes': memory['SwapTotal'],
              'host_swap_free_bytes': memory['SwapFree'],
              'root_free_bytes': shutil.disk_usage('/').free,
              'data_free_bytes': shutil.disk_usage('/srv/echomind').free,
              'containers': {}}
    for service in ('backend', 'proxy'):
        item = json.loads(subprocess.check_output(
            ['docker', 'inspect', f'echomind-{service}-1'], stderr=subprocess.DEVNULL))[0]
        group = Path(f"/sys/fs/cgroup/system.slice/docker-{item['Id']}.scope")
        events = read_pairs(group / 'memory.events')
        values['containers'][service] = {
            'generation': item['Id'],
            'running': item['State']['Running'],
            'healthy': item['State']['Health']['Status'] == 'healthy',
            'oom_killed': item['State']['OOMKilled'], 'restarts': item['RestartCount'],
            'memory_bytes': int((group / 'memory.current').read_text()),
            'lifetime_memory_peak_bytes': int((group / 'memory.peak').read_text()),
            'memory_limit_bytes': item['HostConfig']['Memory'],
            'cpu_usage_usec': read_pairs(group / 'cpu.stat')['usage_usec'],
            'memory_limit_events': events.get('max', 0),
            'oom_events': events.get('oom', 0), 'oom_kill_events': events.get('oom_kill', 0),
        }
    return values


def summarize(samples):
    first, last = samples[0], samples[-1]
    seconds = last['monotonic'] - first['monotonic']
    intervals = []
    for previous, current in zip(samples, samples[1:]):
        total = current['host_cpu_total'] - previous['host_cpu_total']
        idle = current['host_cpu_idle'] - previous['host_cpu_idle']
        if total > 0:
            intervals.append(100 * (1 - idle / total))
    report = {'started_at': first['at'], 'ended_at': last['at'], 'samples': len(samples),
              'elapsed_seconds': round(seconds, 3),
              'sample_interval_cpu_peak_percent': round(max(intervals, default=0), 2),
              'host_memory_total_bytes': first['host_memory_total_bytes'],
              'host_memory_available_min_bytes': min(s['host_memory_available_bytes'] for s in samples),
              'host_swap_used_max_bytes': max(s['host_swap_total_bytes'] - s['host_swap_free_bytes'] for s in samples),
              'root_free_min_bytes': min(s['root_free_bytes'] for s in samples),
              'data_free_min_bytes': min(s['data_free_bytes'] for s in samples),
              'containers': {}}
    for name in ('backend', 'proxy'):
        start, end = first['containers'][name], last['containers'][name]
        cpu_seconds = (end['cpu_usage_usec'] - start['cpu_usage_usec']) / 1_000_000
        report['containers'][name] = {
            'container_replaced': start['generation'] != end['generation'],
            'healthy_at_end': end['running'] and end['healthy'],
            'unhealthy_samples': sum(not (s['containers'][name]['running'] and s['containers'][name]['healthy']) for s in samples),
            'oom_killed': any(s['containers'][name]['oom_killed'] for s in samples),
            'restarts_before': start['restarts'], 'restarts_after': end['restarts'],
            'memory_at_start_bytes': start['memory_bytes'], 'memory_at_end_bytes': end['memory_bytes'],
            'sampled_memory_peak_bytes': max(s['containers'][name]['memory_bytes'] for s in samples),
            'lifetime_memory_peak_before_bytes': start['lifetime_memory_peak_bytes'],
            'lifetime_memory_peak_after_bytes': end['lifetime_memory_peak_bytes'],
            'memory_limit_bytes': end['memory_limit_bytes'],
            'cpu_seconds': round(cpu_seconds, 3),
            'average_cpu_percent_of_two_vcpus': round(100 * cpu_seconds / seconds / 2, 2) if seconds else None,
            **{f'{key}_delta': end[key] - start[key] for key in
               ('memory_limit_events', 'oom_events', 'oom_kill_events')},
        }
    report['load_guard_ok'] = (report['host_memory_available_min_bytes'] >= 192 * 1024**2
        and all(c['sampled_memory_peak_bytes'] < .9 * c['memory_limit_bytes']
                and not c['unhealthy_samples'] and not c['oom_killed']
                and c['restarts_before'] == c['restarts_after']
                and not c['container_replaced'] and c['cpu_seconds'] >= 0
                and not c['oom_events_delta'] and not c['oom_kill_events_delta']
                and not c['memory_limit_events_delta']
                for c in report['containers'].values()))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=600)
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path)
    args = parser.parse_args()
    if not 0 <= args.duration <= 1800 or not 1 <= args.interval <= 30:
        parser.error('Use duration 0..1800 seconds and interval 1..30 seconds.')
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    samples = []
    started = time.monotonic()
    while True:
        samples.append(sample())
        report = summarize(samples)
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(args.output)
        if (not report['load_guard_ok'] or time.monotonic() - started >= args.duration
                or (args.stop_file and args.stop_file.exists())):
            break
        time.sleep(args.interval)
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Capacity observation unavailable; private diagnostics suppressed.')
        raise SystemExit(1) from None
