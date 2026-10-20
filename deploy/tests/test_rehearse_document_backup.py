"""Verify isolated restore and rejection without any database or real document."""
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'operations'))
for parent in Path(__file__).resolve().parents:
    candidate = parent / 'echomind-backend'
    if (candidate / 'app').is_dir():
        sys.path.insert(0, str(candidate))
        break
from rehearse_document_backup import rehearse_archive


class ArchiveRehearsalTest(unittest.TestCase):
    content = b'Synthetic restore test only.'
    row = {'tenant_id':'11111111-1111-4111-8111-111111111111',
           'id':'22222222-2222-4222-8222-222222222222',
           'sha256':hashlib.sha256(content).hexdigest(),'size_bytes':len(content)}

    def archive(self, *, content=None, extra=False, traversal=False):
        stream = BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            data = self.content if content is None else content
            tenant = hashlib.sha256(self.row['tenant_id'].encode()).hexdigest()[:32]
            document = hashlib.sha256(self.row['id'].encode()).hexdigest()[:32]
            name = f'{tenant}/{document}/original.bin'
            if traversal:
                name = '../original.bin'
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info,BytesIO(data))
            if extra:
                info = tarfile.TarInfo(f'{tenant}/33333333333343338333333333333333/original.bin')
                info.size = len(data)
                archive.addfile(info,BytesIO(data))
        return stream.getvalue()

    def test_restores_only_to_a_new_directory_and_removes_it(self):
        with tempfile.TemporaryDirectory() as parent:
            sentinel = Path(parent)/'live-original.bin'
            sentinel.write_bytes(b'Untouched live sentinel')
            result = rehearse_archive(self.archive(),[self.row],temporary_parent=parent)
            self.assertEqual(result['restored_originals'],1)
            self.assertTrue(result['all_hashes_and_sizes_match'])
            self.assertTrue(result['temporary_directory_removed'])
            self.assertEqual(list(Path(parent).iterdir()),[sentinel])
            self.assertEqual(sentinel.read_bytes(),b'Untouched live sentinel')

    def test_rejects_changed_bytes_and_cleans_up_on_failure(self):
        with tempfile.TemporaryDirectory() as parent:
            with self.assertRaises(Exception):
                rehearse_archive(self.archive(content=b'tampered'),[self.row],temporary_parent=parent)
            self.assertEqual(list(Path(parent).iterdir()),[])

    def test_rejects_unexpected_documents(self):
        with self.assertRaises(ValueError):
            rehearse_archive(self.archive(extra=True),[self.row])

    def test_rejects_path_traversal(self):
        with self.assertRaises(Exception):
            rehearse_archive(self.archive(traversal=True),[self.row])


if __name__ == '__main__':
    unittest.main()
