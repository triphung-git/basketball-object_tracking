import hashlib
import json
from zipfile import ZipFile

import pytest

from basketball_scoreboard import full_match_demo as full_match


@pytest.fixture
def demo_archive(tmp_path, monkeypatch):
    video = b"fixture video"
    video_hash = hashlib.sha256(video).hexdigest()
    monkeypatch.setattr(full_match, "FULL_MATCH_VIDEO_SHA256", video_hash)
    monkeypatch.setattr(full_match, "FULL_MATCH_VIDEO_BYTES", len(video))
    files = {name: b"{}" for name in full_match.FULL_MATCH_FILES}
    files.update({
        "input.mp4": video,
        "job.json": json.dumps(dict(id=full_match.FULL_MATCH_JOB_ID, status="completed",
                                    source_sha256=video_hash)).encode(),
    })
    manifest = dict(
        total_files=len(files),
        total_bytes=sum(map(len, files.values())),
        files=[dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
               for name, data in files.items()],
    )
    archive = tmp_path / "demo.zip"
    with ZipFile(archive, "w") as output:
        for name, data in files.items():
            output.writestr(name, data)
        output.writestr("manifest.json", json.dumps(manifest))
    return archive


def spec(archive):
    data = archive.read_bytes()
    return dict(url=archive.as_uri(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def test_install_verifies_archive_and_keeps_local_edits(tmp_path, demo_archive):
    uploads = tmp_path / "uploads"
    release = spec(demo_archive)
    job_id = full_match.install_full_match_demo(uploads, release)
    assert job_id == full_match.FULL_MATCH_JOB_ID
    target = uploads / job_id
    assert full_match.full_match_present(target)
    assert not (target / "manifest.json").exists()

    roster = target / "roster.json"
    roster.write_text('{"local": "edited"}', encoding="utf-8")
    release["url"] = (tmp_path / "unavailable.zip").as_uri()
    assert full_match.install_full_match_demo(uploads, release) == job_id
    assert json.loads(roster.read_text(encoding="utf-8")) == {"local": "edited"}
    assert not (uploads / "demo.json").exists()


def test_bad_archive_digest_leaves_no_partial_job(tmp_path, demo_archive):
    uploads = tmp_path / "uploads"
    release = dict(spec(demo_archive), sha256="0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        full_match.install_full_match_demo(uploads, release)
    assert not list(uploads.iterdir())


def test_archive_rejects_unexpected_paths(tmp_path, demo_archive):
    uploads = tmp_path / "uploads"
    with ZipFile(demo_archive, "a") as output:
        output.writestr("../unexpected", "unexpected")
    with pytest.raises(ValueError, match="Unexpected files"):
        full_match.install_full_match_demo(uploads, spec(demo_archive))
    assert not list(uploads.iterdir())
