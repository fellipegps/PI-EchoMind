"""Register the verified running manual installation as the first rollback target.

No application replacement, secret changes, database writes or image deletion.
Run as root on the existing host after reviewing/transferring this public source.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import tempfile

from rollout import Host, PRIVATE, ROOT, ReleaseError, atomic_json, command, private_file, settings


def baseline(metadata, containers, release: Path, values):
    revision = metadata['source_revision']
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ReleaseError('Invalid existing source revision.')
    if len(containers) != 2:
        raise ReleaseError('Require the existing backend and proxy.')
    for name, item in zip(('backend', 'proxy'), containers):
        if (item['Name'] != '/echomind-' + name + '-1'
                or item['Config']['Labels'].get('com.docker.compose.project') != 'echomind'
                or not item['State']['Running'] or item['State']['Health']['Status'] != 'healthy'
                or metadata['images'][name]['id'] != item['Image']
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', item['Image'])):
            raise ReleaseError('Running installation differs from its verified manual manifest.')
    if containers[0]['Config']['Labels'].get('com.docker.compose.project.working_dir') != metadata['source_directory'] + '/deploy':
        raise ReleaseError('Running backend disagrees with the manual source directory.')
    return {'version': 1, 'origin': 'manual-adoption', 'revision': revision,
            'backend': containers[0]['Image'], 'proxy': containers[1]['Image'],
            'release': str(release), 'settings': values}


def adopt():
    if os.geteuid() != 0 or not all(os.path.ismount(path) for path in (ROOT, PRIVATE)):
        raise ReleaseError('Require root and both existing durable mounts.')
    if (ROOT / 'pending.json').exists() or (ROOT / 'manual-rollout/pending.json').exists():
        raise ReleaseError('Resolve interrupted operations before adoption.')
    manual = ROOT / 'manual-current.json'
    private_file(manual)
    metadata = json.loads(manual.read_text())
    revision = metadata['source_revision']
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ReleaseError('Require the verified existing source revision.')
    source = ROOT / 'releases' / revision
    if source.resolve() != source or metadata['source_directory'] != str(source):
        raise ReleaseError('Manual source must be in the protected release store.')
    release = ROOT / 'releases' / ('manual-' + revision)
    environment = {'PATH': os.defpath + ':/usr/local/bin:/snap/bin', 'HOME': '/root'}
    containers = [json.loads(command(['docker', 'inspect', 'echomind-' + name + '-1'], env=environment))[0]
                  for name in ('backend', 'proxy')]
    state = baseline(metadata, containers, release, settings())
    current = ROOT / 'current.json'
    if current.exists() and json.loads(current.read_text()) != state:
        raise ReleaseError('Pipeline already has a different registered release; do not overwrite it.')
    files = {}
    for name in ('compose.yaml', 'compose.https.yaml'):
        path = source / 'deploy' / name
        if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
            raise ReleaseError('Require regular committed Compose inputs.')
        files[name] = path.read_bytes()
    manifest = {key: state[key] for key in ('version', 'origin', 'revision', 'backend', 'proxy')}
    if release.exists():
        private_file(release / 'manifest.json')
        if json.loads((release / 'manifest.json').read_text()) != manifest or any(
                (release / name).read_bytes() != data for name, data in files.items()):
            raise ReleaseError('Existing adoption directory differs; reconcile privately.')
    else:
        with tempfile.TemporaryDirectory(prefix='adopt-', dir=ROOT / 'releases') as directory:
            staged = Path(directory) / 'baseline'
            staged.mkdir(mode=0o700)
            for name, data in files.items():
                (staged / name).write_bytes(data)
                (staged / name).chmod(0o600)
            atomic_json(staged / 'manifest.json', manifest)
            staged.rename(release)
    host = Host(environment)
    host.preflight(state)
    host.healthy(state)
    atomic_json(current, state)
    print(json.dumps({'manual_revision_registered': revision, 'pinned_local_images': True,
                      'current_release_saved': True, 'application_restarted': False,
                      'database_writes': False, 'runtime_secrets_changed': False}))


if __name__ == '__main__':
    try:
        import fcntl
        os.umask(0o077)
        with (ROOT / 'deploy.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            adopt()
    except Exception:
        print('Manual adoption failed; existing application preserved. Inspect private state.')
        raise SystemExit(1) from None
