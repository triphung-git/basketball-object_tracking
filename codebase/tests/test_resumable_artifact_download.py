"""Range identity, refreshed URL reuse, and checksum safeguards."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('resumable_artifact_download', Path(__file__).resolve().parents[1]/'scripts/resumable_artifact_download.py')
downloader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(downloader)


def binding(url='old', etag='"stable"'):
    return dict(url_sha256=hashlib.sha256(url.encode()).hexdigest(),
                start=0, end=2, total=3, etag=etag)


def test_refreshed_url_reuses_same_strong_etag(tmp_path):
    part = tmp_path/'archive.part0'
    part.write_bytes(b'abc')
    part.with_suffix('.part0.json').write_text(json.dumps(binding()))
    assert downloader.reusable_part(part, binding(url='refreshed'))
    assert not downloader.reusable_part(part, binding(url='refreshed', etag='"changed"'))


def test_weak_etag_does_not_allow_changed_url(tmp_path):
    part = tmp_path/'archive.part0'
    part.write_bytes(b'abc')
    part.with_suffix('.part0.json').write_text(json.dumps(binding(etag='W/"weak"')))
    assert not downloader.reusable_part(part, binding(url='new', etag='W/"weak"'))


def test_tampered_chunk_is_not_reused(tmp_path):
    part = tmp_path/'archive.part0'
    part.write_bytes(b'xyz')
    metadata = binding()
    metadata['sha256'] = hashlib.sha256(b'abc').hexdigest()
    part.with_suffix('.part0.json').write_text(json.dumps(metadata))
    assert not downloader.reusable_part(part, binding())


def range_server(payload):
    class Response(io.BytesIO):
        status = 206
        def __init__(self, start, end):
            super().__init__(payload[start:end+1])
            self.headers = {'Content-Range':f'bytes {start}-{end}/{len(payload)}', 'ETag':'"stable"'}
    def open_url(request, timeout):
        value = request.get_header('Range').removeprefix('bytes=')
        start, end = map(int, value.split('-'))
        return Response(start, end)
    return open_url


def test_ranges_assemble_exactly_and_report_completed(tmp_path, monkeypatch):
    payload = b'0123456789abcdefghijklmnopqrstuvwxyz'
    monkeypatch.setattr(downloader.urllib.request, 'urlopen', range_server(payload))
    destination = tmp_path/'artifact.bin'
    progress = tmp_path/'progress.json'
    result = downloader.download('https://example.test/object', destination, workers=3,
                                 chunk_size=8, progress_path=progress,
                                 expected_sha256=hashlib.sha256(payload).hexdigest())
    assert destination.read_bytes() == payload
    assert result['completed_bytes'] == len(payload)
    assert json.loads(progress.read_text())['status'] == 'completed'
    assert not list(tmp_path.glob('*.part*'))


def test_bad_official_checksum_preserves_existing_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader.urllib.request, 'urlopen', range_server(b'new data'))
    destination = tmp_path/'artifact.bin'
    destination.write_bytes(b'existing')
    with pytest.raises(ValueError, match='SHA256 differs'):
        downloader.download('https://example.test/object', destination, workers=2,
                            chunk_size=4, expected_sha256='0'*64)
    assert destination.read_bytes() == b'existing'
    assert json.loads(destination.with_suffix('.progress.json').read_text())['status'] == 'failed'
