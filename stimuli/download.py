"""Fetch the existing pinned source manifest without credentials or overwrites."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def download(entry, root):
    relative = Path(entry['file'])
    root = Path(root).resolve()
    if relative.is_absolute() or '..' in relative.parts or relative.parts[:2] != ('stimuli', 'raw'):
        raise ValueError('Source destination must stay within stimuli/raw')
    target = (root/relative).resolve()
    target.relative_to(root/'stimuli'/'raw')
    url = urlparse(entry['url'])
    if url.scheme != 'https' or url.username or url.password:
        raise ValueError('Public HTTPS source required')
    def verify(path):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
        if path.stat().st_size != entry['bytes'] or digest.hexdigest() != entry['sha256']:
            raise ValueError('Source size/hash mismatch: '+str(relative))
    if target.exists():
        verify(target)
        return 'verified existing'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            request = Request(entry['url'], headers={'User-Agent': 'jev-audit-source-fetch/1.0'})
            with urlopen(request, timeout=60) as response:
                size = 0
                for chunk in iter(lambda: response.read(1024*1024), b''):
                    size += len(chunk)
                    if size > entry['bytes']: raise ValueError('Source exceeds pinned byte count')
                    output.write(chunk)
        verify(temporary)
        os.link(temporary, target)  # Atomic creation; a concurrent existing file is not replaced.
        return 'downloaded and verified'
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    for source in json.loads(Path('stimuli/sources.json').read_text()):
        print(source['file']+': '+download(source, Path.cwd()), flush=True)
