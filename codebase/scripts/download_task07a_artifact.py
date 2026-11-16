"""Download one private Roboflow artifact without logging its URL."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request
from urllib.parse import urlsplit


def download(url, destination, workers):
    partial = destination.with_suffix(destination.suffix + '.partial')
    request = urllib.request.Request(url, headers={'User-Agent': 'Python', 'Range': 'bytes=0-0'})
    with urllib.request.urlopen(request, timeout=120) as response:
        content_range = response.headers.get('Content-Range', '')
        if response.status != 206 or not content_range.startswith('bytes 0-0/'):
            # A server that ignores ranges must be streamed once, never concatenated.
            with partial.open('wb') as stream:
                shutil.copyfileobj(response, stream, 1024 * 1024)
            partial.replace(destination)
            return
        total = int(content_range.split('/')[-1])
        etag = response.headers.get('ETag')
    chunk_size = 1024 * 1024
    part_count = (total + chunk_size - 1) // chunk_size

    def download_part(index):
        start, end = index * chunk_size, min(total, (index + 1) * chunk_size) - 1
        target = destination.with_suffix(destination.suffix + f'.part{index}')
        binding_path = target.with_suffix(target.suffix + '.json')
        binding = dict(url_sha256=hashlib.sha256(url.encode()).hexdigest(), start=start, end=end,
                       total=total, etag=etag)
        if (target.is_file() and target.stat().st_size == end - start + 1 and binding_path.is_file()
                and json.loads(binding_path.read_text()) == binding):
            return target
        request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}',
                                                       'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=90) as response, target.open('wb') as stream:
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}':
                print('Range mismatch:', index, response.status, response.headers.get('Content-Range'), flush=True)
                raise ValueError('Range response differs')
            shutil.copyfileobj(response, stream, 64 * 1024)
        if target.stat().st_size != end - start + 1:
            raise ValueError('Incomplete range')
        binding_path.write_text(json.dumps(binding), encoding='utf-8')
        return target

    def part(index):
        for attempt in range(4):
            try:
                return download_part(index)
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))

    parts = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index, path in enumerate(executor.map(part, range(part_count)), start=1):
            parts.append(path)
            if index % 50 == 0:
                print(f'Downloaded parts: {index}/{part_count}', flush=True)
    with partial.open('wb') as stream:
        for path in parts:
            with path.open('rb') as source:
                shutil.copyfileobj(source, stream, 1024 * 1024)
    if partial.stat().st_size != total:
        raise ValueError('Incomplete assembled artifact')
    partial.replace(destination)
    for path in parts:
        path.unlink()
        path.with_suffix(path.suffix+'.json').unlink()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, choices=range(1,17), default=8)
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    destination = Path(args.output)
    partial = destination.with_suffix(destination.suffix + '.partial')
    try:
        url = os.environ['TASK07A_ARTIFACT_URL']
        if not url.startswith('https://'):
            raise ValueError('HTTPS required')
        if args.inspect:
            request = urllib.request.Request(url, headers={'Range': 'bytes=1-1'})
            with urllib.request.urlopen(request, timeout=30) as response:
                print(dict(host=urlsplit(response.geturl()).hostname, status=response.status,
                           content_range=response.headers.get('Content-Range'),
                           content_length=response.headers.get('Content-Length')))
            sys.exit(0)
        download(url, destination, args.workers)
        print('Downloaded bytes:', destination.stat().st_size)
    except Exception as error:
        print('Download failed:', type(error).__name__, file=sys.stderr)
        sys.exit(1)
