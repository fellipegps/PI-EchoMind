"""Measure real E5 inside the existing Linux production image with synthetic data.

Downloads only the public model to a dedicated Docker cache volume. Never reads
env files or contacts AWS, Supabase or Groq. Keeps the public cache for warm runs.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid

DEPLOY = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='echomind-backend:deploy-step7')
    parser.add_argument('--memory', default='1536m')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cold', action='store_true', help='Use and remove a fresh public model cache')
    args = parser.parse_args()
    name = 'echomind-e5-measure-' + uuid.uuid4().hex[:12]
    cache_volume = name + '-models' if args.cold else 'echomind-e5-measure-models'
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('AWS_', 'HF_', 'HUGGING_FACE_', 'SUPABASE_', 'GROQ_', 'DATABASE_'))}
    command = ['docker', 'run', '--name', name, '--pull', 'never', '--platform', 'linux/amd64',
               '--memory', args.memory, '--memory-swap', args.memory, '--cpus', '2',
               '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
               '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m,mode=1777',
               '--mount', f'type=volume,source={cache_volume},target=/var/cache/echomind/models',
               '--mount', f'type=bind,source={DEPLOY / "fixtures/measure_e5.py"},target=/measure.py,readonly']
    synthetic = {
        'ECHOMIND_ENV': 'testing', 'DATABASE_URL': 'postgresql://synthetic:synthetic@127.0.0.1:1/synthetic',
        'SUPABASE_URL': 'https://synthetic.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_synthetic',
        'GROQ_API_KEY': 'gsk_synthetic', 'RAG_WARMUP_ENABLED': 'false', 'DOCUMENT_RECOVERY_ENABLED': 'false',
        'RERANKER_ENABLED': 'false', 'ALLOWED_ORIGINS': 'https://synthetic.example.test',
        'HF_HUB_DISABLE_TELEMETRY': '1', 'HF_HUB_DISABLE_PROGRESS_BARS': '1',
    }
    for key, value in synthetic.items():
        command.extend(['--env', f'{key}={value}'])
    command.extend([args.image, 'python', '/measure.py'])
    phases = []
    try:
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace', bufsize=1)
        for line in process.stdout:
            print(line, end='', flush=True)
            try:
                value = json.loads(line)
                if isinstance(value, dict) and 'phase' in value:
                    phases.append(value)
            except ValueError:
                pass
        code = process.wait()
        inspected = subprocess.run(['docker', 'inspect', name], capture_output=True, check=True, env=environment)
        state = json.loads(inspected.stdout)[0]['State']
        report = {'image': args.image, 'memory_limit': args.memory, 'cpus': 2, 'swap_enabled': False, 'fresh_cache': args.cold,
                  'exit_code': code, 'oom_killed': state['OOMKilled'], 'phases': phases,
                  'limitations': ['Synthetic document/query encoding; no LLM, database, auth or HTTP requests.',
                                  'Docker CPU quota is not an EC2 t3.small baseline/credit performance measurement.',
                                  'A 10 MiB TXT is chunked but only 40 document chunks and 20 queries are encoded.']}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        if code != 0 or not phases or phases[-1]['phase'] != 'completed':
            raise SystemExit('Measurement failed; inspect the recorded OOM/phase result before sizing.')
    finally:
        subprocess.run(['docker', 'rm', '--force', name], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if args.cold:
            subprocess.run(['docker', 'volume', 'rm', cache_volume], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
