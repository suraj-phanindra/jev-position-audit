import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stimuli.download import download


class SourceDownloadChecks(unittest.TestCase):
    def test_verified_creation_and_failure_preservation(self):
        body = b'public source bytes'
        source = dict(file='stimuli/raw/test.dat', url='https://example.org/test.dat',
                      bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root/source['file']
            with patch('stimuli.download.urlopen', return_value=io.BytesIO(body)):
                self.assertEqual(download(source, root), 'downloaded and verified')
            with patch('stimuli.download.urlopen') as network:
                self.assertEqual(download(source, root), 'verified existing')
                network.assert_not_called()
            target.write_bytes(b'preserve a conflicting file')
            with self.assertRaises(ValueError): download(source, root)
            self.assertEqual(target.read_bytes(), b'preserve a conflicting file')
            target.unlink()
            for invalid in (b'wrong', body+b'extra'):
                with patch('stimuli.download.urlopen', return_value=io.BytesIO(invalid)):
                    with self.assertRaises(ValueError): download(source, root)
                self.assertEqual(list(target.parent.iterdir()), [])
            for name in ('../outside', '/tmp/outside', 'stimuli/raw/../../.env'):
                with self.assertRaises(ValueError): download({**source, 'file': name}, root)
            for url in ('http://example.org/test.dat', 'https://user:secret@example.org/test.dat'):
                with self.assertRaises(ValueError): download({**source, 'url': url}, root)


if __name__ == '__main__': unittest.main()
