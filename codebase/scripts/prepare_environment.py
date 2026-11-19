"""Automated resource verification and environment preparation for basketball tracking."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def sha256_file(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def matches_model(path: Path, entry: dict) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == entry["size_bytes"]
        and sha256_file(path) == entry["sha256"]
    )


def restore_model(target: Path, entry: dict) -> None:
    source_url = entry["source_url"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=target.parent) as scratch:
        downloaded = Path(scratch) / "download"
        with urlopen(source_url, timeout=60) as response, downloaded.open("wb") as out:
            shutil.copyfileobj(response, out)
        candidate = downloaded
        if source_url.endswith(".zip"):
            candidate = Path(scratch) / target.name
            with ZipFile(downloaded) as archive, archive.open(target.name) as member:
                if archive.getinfo(target.name).file_size != entry["size_bytes"]:
                    raise ValueError("Unexpected size for the archived model")
                with candidate.open("wb") as out:
                    shutil.copyfileobj(member, out)
        if not matches_model(candidate, entry):
            raise ValueError("Downloaded model failed SHA-256 verification")
        candidate.replace(target)


def verify_models(models_dir: Path) -> bool:
    manifest_path = models_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["files"]
        if (not entries or len(entries) != manifest["total_files"]
                or sum(entry["size_bytes"] for entry in entries) != manifest["total_bytes"]):
            raise ValueError("Model manifest file count or size mismatch")
        print(f"[*] Checking {len(entries)} model artifacts against manifest...")
        root = models_dir.resolve()
        for entry in entries:
            rel = entry["relative_path"]
            target = (root / rel).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"Model path is outside the models folder: {rel}")
            if not matches_model(target, entry):
                if not entry.get("source_url"):
                    raise ValueError(f"Missing or damaged bundled model: {rel}. Restore it from Git.")
                print(f"  [*] Restoring {rel} from its source...")
                restore_model(target, entry)
            print(f"  [OK] {rel} (SHA-256 verified)")
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as exc:
        print(f"[ERROR] Model verification failed: {exc}")
        return False
    return True


def verify_demo(uploads_dir: Path) -> bool:
    from basketball_scoreboard.demo_bundle import install_dashboard_demo

    try:
        job_id = install_dashboard_demo(ROOT / "demo", uploads_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[ERROR] Demo verification failed: {exc}")
        return False
    print(f"  [OK] Dashboard demo {job_id} verified and ready.")
    return True


def verify_imports() -> bool:
    print("[*] Verifying Python runtime dependencies...")
    packages = [
        ("av", "av"),
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("onnxruntime", "onnxruntime"),
        ("scipy", "scipy"),
        ("matplotlib", "matplotlib"),
        ("yaml", "PyYAML"),
        ("torch", "torch"),
        ("easyocr", "easyocr"),
    ]
    for mod_name, pkg_name in packages:
        try:
            mod = __import__(mod_name)
            ver = getattr(mod, "__version__", None)
            if not ver:
                try:
                    ver = importlib.metadata.version(pkg_name)
                except Exception:
                    ver = "available"
            print(f"  [OK] {pkg_name} ({ver})")
        except ImportError as exc:
            print(f"[ERROR] Failed to import {pkg_name} ({mod_name}): {exc}")
            return False
    return True


def verify_runtime_execution() -> bool:
    print("[*] Testing local model and OCR initialization...")
    from basketball_scoreboard.detector import ObjectDetector
    from basketball_scoreboard.identity import LocalEasyOCRProvider

    t0 = time.perf_counter()
    detector = ObjectDetector()
    warmup_times = detector.warmup()
    det_time = time.perf_counter() - t0
    print(f"  [OK] YOLO26 ONNX Detector initialized & warmed up ({det_time:.2f}s, warmup: {[round(x,1) for x in warmup_times]}ms)")

    t0 = time.perf_counter()
    ocr = LocalEasyOCRProvider()
    _ = ocr.reader
    ocr_time = time.perf_counter() - t0
    print(f"  [OK] Local EasyOCR initialized ({ocr_time:.2f}s)")
    return True


def main() -> int:
    print("=" * 65)
    print("  BASKETBALL OBJECT TRACKING & SPATIAL DASHBOARD SETUP CHECK")
    print("=" * 65)

    models_dir = ROOT / "models"
    if not verify_models(models_dir):
        return 1

    uploads_dir = ROOT / "outputs" / "web-uploads"
    if not verify_demo(uploads_dir):
        return 1

    try:
        if not verify_imports() or not verify_runtime_execution():
            return 1
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] Could not initialize the local detector or OCR: {exc}")
        return 1

    print("=" * 65)
    print("  SETUP COMPLETE & VERIFIED!")
    print("  You can now launch the dashboard by running:")
    print("    .\\start_dashboard.bat")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
