"""Resume an HTTPS artifact by verified byte ranges, without logging private URLs."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import urllib.request


def file_digest(path, algorithm='sha256'):
    digest = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.1)


def reusable_part(target, binding):
    """A refreshed signed URL may reuse the same strongly identified object."""
    metadata = target.with_suffix(target.suffix + '.json')
    if not target.is_file() or not metadata.is_file():
        return False
    try:
        old = json.loads(metadata.read_text(encoding='utf-8-sig'))
        if any(old.get(key) != binding[key] for key in ('start', 'end', 'total')):
            return False
        if target.stat().st_size != binding['end'] - binding['start'] + 1:
            return False
        strong = bool(binding['etag']) and not binding['etag'].startswith('W/')
        if strong:
            if old.get('etag') != binding['etag']:
                return False
        elif old.get('url_sha256') != binding['url_sha256']:
            return False
        return not old.get('sha256') or file_digest(target) == old['sha256']
    except (OSError, ValueError, KeyError):
        return False


def download(url, destination, workers=8, progress_path=None, chunk_size=1024*1024,
             expected_sha256=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    progress_path = Path(progress_path) if progress_path else destination.with_suffix('.progress.json')
    progress = dict(status='connecting', pid=os.getpid(), completed_bytes=0,
                    completed_parts=0, resumed_parts=0)
    started = time.monotonic()

    def publish(**values):
        progress.update(values, updated_utc=datetime.now(timezone.utc).isoformat())
        progress['elapsed_seconds'] = round(time.monotonic() - started, 1)
        atomic_json(progress_path, progress)

    publish()
    request = urllib.request.Request(url, headers={'Range': 'bytes=0-0', 'User-Agent': 'Python'})
    with urllib.request.urlopen(request, timeout=90) as response:
        content_range = response.headers.get('Content-Range', '')
        if response.status != 206 or not content_range.startswith('bytes 0-0/'):
            raise ValueError('This resumable download requires HTTP range support')
        total = int(content_range.split('/')[-1])
        etag = response.headers.get('ETag')
    count = (total + chunk_size - 1) // chunk_size
    publish(status='downloading', total_bytes=total, total_parts=count, etag=etag)
    cancelled = threading.Event()

    def part(index):
        start, end = index * chunk_size, min(total, (index + 1) * chunk_size) - 1
        target = destination.with_suffix(destination.suffix + f'.part{index}')
        metadata = target.with_suffix(target.suffix + '.json')
        binding = dict(url_sha256=hashlib.sha256(url.encode()).hexdigest(),
                       start=start, end=end, total=total, etag=etag)
        if reusable_part(target, binding):
            return target, True
        metadata.unlink(missing_ok=True)
        for attempt in range(6):
            if cancelled.is_set():
                raise InterruptedError('Download cancelled')
            try:
                headers = {'Range': f'bytes={start}-{end}', 'Cache-Control': 'no-cache'}
                if etag and not etag.startswith('W/'):
                    headers['If-Match'] = etag
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=60) as response, target.open('wb') as stream:
                    if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}':
                        raise ValueError('Range response differs')
                    if etag and response.headers.get('ETag') not in (None, etag):
                        raise ValueError('Object changed during download')
                    while data := response.read(64 * 1024):
                        if cancelled.is_set():
                            raise InterruptedError('Download cancelled')
                        stream.write(data)
                if target.stat().st_size != end - start + 1:
                    raise ValueError('Incomplete range')
                binding['sha256'] = file_digest(target)
                atomic_json(metadata, binding)
                return target, False
            except Exception:
                if attempt == 5 or cancelled.is_set():
                    raise
                cancelled.wait(min(2 ** attempt, 16))

    paths = {}
    last_publish = 0
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(part, index): index for index in range(count)}
            try:
                for future in as_completed(futures):
                    index = futures[future]
                    target, resumed = future.result()
                    paths[index] = target
                    progress['completed_bytes'] += target.stat().st_size
                    progress['completed_parts'] += 1
                    progress['resumed_parts'] += int(resumed)
                    if time.monotonic() - last_publish >= 2 or len(paths) == count or len(paths) % 50 == 0:
                        publish(percent=round(100 * progress['completed_bytes'] / total, 2))
                        last_publish = time.monotonic()
                    if len(paths) % 50 == 0:
                        print(f'Completed parts: {len(paths)}/{count}', flush=True)
            except BaseException:
                cancelled.set()
                for future in futures:
                    future.cancel()
                raise
        publish(status='assembling')
        partial = destination.with_suffix(destination.suffix + '.partial')
        with partial.open('wb') as stream:
            for index in range(count):
                with paths[index].open('rb') as source:
                    shutil.copyfileobj(source, stream, 1024 * 1024)
        if partial.stat().st_size != total:
            raise ValueError('Assembled artifact length differs')
        digest = file_digest(partial)
        if expected_sha256 and digest.lower() != expected_sha256.lower():
            raise ValueError('Artifact SHA256 differs from official index')
        partial.replace(destination)
        publish(status='completed', sha256=digest, percent=100)
        for path in paths.values():
            path.unlink()
            path.with_suffix(path.suffix + '.json').unlink()
        return progress
    except BaseException as error:
        publish(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                error_type=type(error).__name__)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, choices=range(1,33), default=8)
    parser.add_argument('--progress')
    parser.add_argument('--chunk-mb', type=int, choices=range(1,17), default=1)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    try:
        url = os.environ['TASK07A_ARTIFACT_URL']
        if not url.startswith('https://'):
            raise ValueError('HTTPS required')
        result = download(url, Path(args.output), args.workers, args.progress,
                          args.chunk_mb * 1024 * 1024, args.sha256)
        print('Downloaded bytes:', result['total_bytes'], flush=True)
    except Exception as error:
        print('Download failed:', type(error).__name__, file=sys.stderr)
        sys.exit(1)
