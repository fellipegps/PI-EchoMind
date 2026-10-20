"""Safety checks without mounting or accessing AWS/private data."""
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'operations'))
from inspect_restored_volume import GIB, compare_originals, select_copy

COPY = 'vol-11111111111111111'
ROOT = 'vol-22222222222222222'
DATA = 'vol-33333333333333333'
NAME = 'a' * 32 + '/' + 'b' * 32 + '/original.bin'


def inventory():
    return {'blockdevices': [dict(path=f'/dev/nvme{index}n1', serial=serial.replace('-', ''),
        type='disk', fstype='ext4', size=20 * GIB, mountpoints=mounts)
        for index, serial, mounts in ((0, COPY, [None]), (1, ROOT, ['/']), (2, DATA, ['/srv/echomind']))]}


def archive(content=b'recovery fixture', name=NAME, symlink=False):
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode='w:') as writer:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        if symlink:
            info.type = tarfile.SYMTYPE
            info.linkname = '/etc/passwd'
        writer.addfile(info, BytesIO(content))
    data = stream.getvalue()
    return data, hashlib.sha256(data).hexdigest()


class CopySafetyTest(unittest.TestCase):
    def test_select_by_volume_serial_not_device_order(self):
        disks = inventory()
        disks['blockdevices'].reverse()
        self.assertEqual(select_copy(disks, COPY, ROOT, DATA), ('/dev/nvme0n1', '/dev/nvme2n1'))
        with self.assertRaises(ValueError):
            select_copy(disks, DATA, ROOT, DATA)

    def test_reject_mounted_partitioned_wrong_size_or_duplicate_serial(self):
        for patch in ({'mountpoints': ['/already-mounted']}, {'children': [{}]},
                      {'size': 16 * GIB}, {'fstype': 'xfs'}, {'type': 'part'}, {'path': '/dev/sdf'}):
            disks = inventory()
            disks['blockdevices'][0].update(patch)
            with self.assertRaises(ValueError):
                select_copy(disks, COPY, ROOT, DATA)
        disks = inventory()
        disks['blockdevices'].append(deepcopy(disks['blockdevices'][0]))
        with self.assertRaises(ValueError):
            select_copy(disks, COPY, ROOT, DATA)

    def test_compare_bytes_and_detect_corruption_or_extra_originals(self):
        data, digest = archive()
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / label for label in ('live', 'copy')]
            for root in roots:
                target = root / NAME
                target.parent.mkdir(parents=True)
                target.write_bytes(b'recovery fixture')
            self.assertEqual(compare_originals(data, digest, *roots)['restored_originals'], 1)
            (roots[1] / NAME).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                compare_originals(data, digest, *roots)
            (roots[1] / NAME).write_bytes(b'recovery fixture')
            (roots[1] / ('a' * 32) / ('c' * 32)).mkdir()
            (roots[1] / ('a' * 32) / ('c' * 32) / 'original.bin').write_bytes(b'extra')
            with self.assertRaises(ValueError):
                compare_originals(data, digest, *roots)

    def test_reject_unpinned_unsafe_or_linked_archive(self):
        for name, symlink in (('../original.bin', False), (NAME, True), ('a/job.json', False)):
            data, digest = archive(name=name, symlink=symlink)
            with self.assertRaises(ValueError):
                compare_originals(data, digest, Path('.'), Path('.'))
        data, _ = archive()
        with self.assertRaises(ValueError):
            compare_originals(data, '0' * 64, Path('.'), Path('.'))


if __name__ == '__main__':
    unittest.main()
