"""Inspect one disposable EBS copy read-only; never restore over the live disk.

Run on the existing Linux host through its authenticated administration channel.
CloudFormation/EC2 snapshot, ownership, tags and attachment checks must precede it.
No credentials, database access, second backend or filesystem journal replay.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile

GIB = 1024 ** 3
MAX_ARCHIVE = 64 * 1024 ** 2
LIVE = Path('/srv/echomind')
MOUNT = Path('/mnt/echomind-restore-drill')


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=60).stdout


def volume_key(value):
    if not re.fullmatch(r'vol-?[0-9a-f]{17}', value):
        raise ValueError('Invalid volume identifier.')
    return value.replace('-', '')


def select_copy(inventory, copy_id, root_id, data_id):
    keys = [volume_key(value) for value in (copy_id, root_id, data_id)]
    if len(set(keys)) != 3:
        raise ValueError('Copy and protected volumes must differ.')
    disks = inventory['blockdevices']
    selected = []
    for key in keys:
        matches = [disk for disk in disks if str(disk.get('serial', '')).replace('-', '') == key]
        if len(matches) != 1:
            raise ValueError('Require one device for each authenticated volume ID.')
        selected.append(matches[0])
    disk = selected[0]
    if (not re.fullmatch(r'/dev/nvme[0-9]+n[0-9]+', disk['path'])
            or disk.get('type') != 'disk' or disk.get('fstype') != 'ext4'
            or int(disk['size']) != 20 * GIB or disk.get('children')
            or any(disk.get('mountpoints') or [])
            or len({item['path'] for item in selected}) != 3):
        raise ValueError('Disposable copy device is not an unused raw 20 GiB ext4 disk.')
    return disk['path'], selected[2]['path']


def confined_file(root, relative):
    root = root.resolve(strict=True)
    path = root / relative
    for part in Path(relative).parts:
        if part in ('.', '..'):
            raise ValueError('Unsafe archive path.')
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError('Unsafe archive path.')
    current = root
    for part in Path(relative).parts:
        current = current / part
        if stat.S_ISLNK(current.lstat().st_mode):
            raise ValueError('Symlinks are not accepted in document paths.')
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Original must be a regular file.')
    return path


def digest_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def compare_originals(data, digest, live, restored):
    if not data or len(data) > MAX_ARCHIVE or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Pinned archive digest or size mismatch.')
    expected = {}
    with tarfile.open(fileobj=BytesIO(data), mode='r:') as archive:
        for member in archive:
            if (not member.isfile() or not re.fullmatch(r'[0-9a-f]{32}/[0-9a-f]{32}/original.bin', member.name)
                    or member.name in expected or member.size > MAX_ARCHIVE):
                raise ValueError('Unexpected archive entry.')
            with archive.extractfile(member) as stream:
                content = stream.read(MAX_ARCHIVE + 1)
            if len(content) != member.size:
                raise ValueError('Archive member size mismatch.')
            expected[member.name] = (len(content), hashlib.sha256(content).hexdigest())
    if not expected:
        raise ValueError('Require an original in the reference archive.')
    for root in (live, restored):
        actual = {path.relative_to(root).as_posix() for path in root.glob('*/*/original.bin')}
        if actual != set(expected) or any(root.glob('*/*/job.json')):
            raise ValueError('Snapshot or live document inventory differs from the reference.')
        for name, reference in expected.items():
            if digest_file(confined_file(root, name)) != reference:
                raise ValueError('Original hash or size mismatch.')
    return {'restored_originals': len(expected), 'all_hashes_and_sizes_match': True,
            'live_and_copy_inventory_match': True, 'pending_jobs': 0}


def inspect(args):
    if os.geteuid() != 0:
        raise ValueError('Run through the host administrator channel.')
    if not re.fullmatch(r'[0-9a-f]{64}', args.archive_sha256):
        raise ValueError('Require a pinned archive hash.')
    archive = Path(args.archive)
    if (archive.parent != LIVE / 'manual-backups' or archive.is_symlink()
            or not re.fullmatch(r'[0-9a-f]{32}\.documents\.tar', archive.name)
            or archive.stat().st_size > MAX_ARCHIVE):
        raise ValueError('Require the existing bounded private archive.')
    inventory = json.loads(command('lsblk', '--tree', '--json', '--bytes', '--output',
                                   'PATH,SERIAL,SIZE,FSTYPE,TYPE,RO,MOUNTPOINTS'))
    device, data_device = select_copy(inventory, args.volume_id, args.root_volume_id, args.data_volume_id)
    live_mount = json.loads(command('findmnt', '--json', '--mountpoint', str(LIVE)))['filesystems']
    if len(live_mount) != 1 or Path(live_mount[0]['source']).resolve() != Path(data_device).resolve():
        raise ValueError('Live data mount differs from the protected source volume.')
    documents = Path(command('docker', 'volume', 'inspect', '--format', '{{.Mountpoint}}',
                             'echomind_documents').strip()).resolve(strict=True)
    relative = documents.relative_to(LIVE.resolve(strict=True))
    if not relative.parts or documents.is_symlink():
        raise ValueError('Document volume must be within the live data disk.')
    if MOUNT.exists() or MOUNT.is_symlink():
        raise ValueError('Require an absent dedicated rehearsal mount directory.')
    if not stat.S_ISBLK(Path(device).stat().st_mode):
        raise ValueError('Copy must be a block device.')
    mounted = False
    removed = False
    MOUNT.mkdir(mode=0o700)
    try:
        command('blockdev', '--setro', device)
        if command('blockdev', '--getro', device).strip() != '1':
            raise ValueError('Copy block device is not read-only.')
        command('mount', '-t', 'ext4', '-o', 'ro,noload,nodev,nosuid,noexec', device, str(MOUNT))
        mounted = True
        mounted_state = json.loads(command('findmnt', '--json', '--mountpoint', str(MOUNT)))['filesystems']
        if (len(mounted_state) != 1
                or Path(mounted_state[0]['source']).resolve() != Path(device).resolve()
                or not {'ro', 'nodev', 'nosuid', 'noexec'} <= set(mounted_state[0]['options'].split(','))):
            raise ValueError('Unexpected recovery mount source or options.')
        # Reject symlinks in the copied path before reading only the document originals.
        current = MOUNT
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('Copied Docker volume path contains a symlink.')
        with archive.open('rb') as stream:
            data = stream.read(MAX_ARCHIVE + 1)
        report = compare_originals(data, args.archive_sha256, documents, MOUNT / relative)
    finally:
        if mounted:
            command('umount', str(MOUNT))
            mounted = False
        # Refuse cleanup or subsequent volume disposal if any mount remains.
        state = json.loads(command('lsblk', '--tree', '--json', '--bytes', '--output',
                                   'PATH,SERIAL,SIZE,FSTYPE,TYPE,RO,MOUNTPOINTS'))
        select_copy(state, args.volume_id, args.root_volume_id, args.data_volume_id)
        MOUNT.rmdir()
        removed = True
    return {**report, 'copy_block_device_read_only': True, 'journal_replayed': False,
            'copy_unmounted': not mounted, 'mount_directory_removed': removed,
            'live_volume_restored': False, 'database_accessed': False,
            'additional_backend_started': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('volume-id', 'root-volume-id', 'data-volume-id', 'archive', 'archive-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args)))
    except Exception:
        print('Read-only EBS inspection failed; private diagnostics suppressed. Verify unmount before disposal.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
