"""Fetch exact Windows CUDA wheels from PyTorch's official index, with resume."""
import argparse
from html.parser import HTMLParser
import html
from pathlib import Path
import sys
import urllib.parse
import urllib.request

from resumable_artifact_download import atomic_json, download, file_digest


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(value for key, value in attrs if key == 'href')


def resolve(package, version):
    index = f'https://download.pytorch.org/whl/cu128/{package}/'
    with urllib.request.urlopen(index, timeout=90) as response:
        parser = Links()
        parser.feed(response.read().decode())
    expected = f'{package}-{version}-cp312-cp312-win_amd64.whl'
    for raw in parser.links:
        url = urllib.parse.urljoin(index, html.unescape(raw))
        parsed = urllib.parse.urlsplit(url)
        if urllib.parse.unquote(Path(parsed.path).name) == expected:
            digest = urllib.parse.parse_qs(parsed.fragment).get('sha256', [None])[0]
            if not digest:
                raise ValueError('Official wheel is missing its SHA256')
            return expected, urllib.parse.urldefrag(url)[0], digest
    raise ValueError('Exact CUDA wheel not found on official index')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--progress-dir', required=True)
    parser.add_argument('--workers', type=int, default=12)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    try:
        for package, version in [('torchvision','0.26.0+cu128'), ('torch','2.11.0+cu128')]:
            filename, url, digest = resolve(package, version)
            path = directory/filename
            print('Fetching', filename, flush=True)
            if not path.is_file() or file_digest(path) != digest:
                download(url, path, workers=args.workers, chunk_size=4*1024*1024,
                         progress_path=Path(args.progress_dir)/(package+'-download.json'),
                         expected_sha256=digest)
            else:
                atomic_json(Path(args.progress_dir)/(package+'-download.json'),
                            dict(status='completed',pid=__import__('os').getpid(),
                                 completed_bytes=path.stat().st_size,total_bytes=path.stat().st_size,
                                 percent=100,sha256=digest,reused_verified_wheel=True))
            manifest.append(dict(package=package, version=version, path=str(path), sha256=digest))
            atomic_json(directory/'manifest.json', manifest)
    except Exception as error:
        print('CUDA wheel fetch failed:', type(error).__name__, file=sys.stderr)
        sys.exit(1)
