"""Bounded local ONNX/CPU smoke test for the project's exact Roboflow model."""
import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.metadata
import io
import json
import logging
import math
import os
from pathlib import Path
import statistics
import time

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1"
EXPECTED_CLASSES = {"ball", "rim", "human"}

def _get_cache_dir():
    cache_path = str(ROOT.resolve() / ".model-cache")
    if os.name == "nt" and not cache_path.startswith("\\\\?\\"):
        cache_path = "\\\\?\\" + cache_path
    return cache_path


CACHE_DIR = _get_cache_dir()
os.environ.setdefault("INFERENCE_HOME", CACHE_DIR)
os.environ.setdefault("DEFAULT_DEVICE", "cpu")


def load_credentials(path):
    """Only read two literal assignments; never evaluate shell code or expand values."""
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if separator and name.strip() in {"ROBOFLOW_API_KEY", "ROBOFLOW_MODEL_ID"}:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[name.strip()] = value
    key = os.environ.get("ROBOFLOW_API_KEY") or values.get("ROBOFLOW_API_KEY", "")
    model_id = os.environ.get("ROBOFLOW_MODEL_ID") or values.get("ROBOFLOW_MODEL_ID", MODEL_ID)
    if model_id != MODEL_ID:
        raise ValueError("Model ID differs from the approved model; review before changing it.")
    if not key or key.strip() in {"your_api_key_here", "<your-key>"}:
        raise ValueError("Missing key: set ROBOFLOW_API_KEY locally or in codebase/.env; never paste it into chat.")
    return key


@contextmanager
def private_library_output():
    # Library exception/log messages can contain authenticated request URLs.
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            yield
    finally:
        logging.disable(previous)


def normalize_detections(boxes, ids, scores, classes, original_wh, input_wh, threshold):
    if not (len(boxes) == len(ids) == len(scores)):
        raise ValueError("Inconsistent detection array lengths")
    width, height = original_wh
    input_width, input_height = input_wh
    records = []
    for box, class_id, score in zip(boxes, ids, scores):
        class_id_number, score = float(class_id), float(score)
        if not math.isfinite(class_id_number) or not class_id_number.is_integer():
            raise ValueError("Invalid class ID")
        class_id = int(class_id_number)
        if class_id < 0 or class_id >= len(classes):
            raise ValueError("Unknown class ID")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Invalid confidence")
        if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
            raise ValueError("Invalid bbox")
        x1, y1, x2, y2 = map(float, box)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Invalid bbox order")
        if score < threshold:
            continue
        x1, x2 = [min(width, max(0, x * width / input_width)) for x in (x1, x2)]
        y1, y2 = [min(height, max(0, y * height / input_height)) for y in (y1, y2)]
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Bbox outside image")
        records.append({"xyxy": [x1, y1, x2, y2], "class_id": class_id,
                        "class_name": classes[class_id], "confidence": score})
    return records


def _apply_windows_symlink_compat():
    """Enable file copy fallback on Windows when unprivileged symlink creation raises WinError 1314, preserving full MD5 verification."""
    cache_dir = _get_cache_dir()
    os.environ["INFERENCE_HOME"] = cache_dir
    os.environ["DEFAULT_DEVICE"] = "cpu"
    try:
        import inference_models.configuration as cfg
        import inference_models.models.auto_loaders.model_cache_paths as mcp
        import inference_models.models.auto_loaders.core as core
        import inference_models.models.auto_loaders.auto_resolution_cache as arc
        import inference_models.weights_providers.offline_registry as ofr

        cfg.INFERENCE_HOME = cache_dir
        mcp.INFERENCE_HOME = cache_dir
        core.INFERENCE_HOME = cache_dir
        arc.INFERENCE_HOME = cache_dir
        ofr.INFERENCE_HOME = cache_dir
    except ImportError:
        return

    if os.name != "nt":
        return

    import shutil

    def safe_handle_symlink_creation(target_path, link_name, **kwargs):
        link_dir = os.path.dirname(os.path.abspath(link_name))
        os.makedirs(link_dir, exist_ok=True)
        try:
            os.symlink(target_path, link_name)
        except OSError as error:
            if getattr(error, "winerror", None) != 1314:
                raise
            # Never turn an unrelated I/O failure into an overwrite.
            with open(target_path, "rb") as source, open(link_name, "xb") as destination:
                shutil.copyfileobj(source, destination)

    def safe_materialize(package_dir, declarations):
        identities = []
        shared_blobs_dir = os.path.abspath(mcp.generate_shared_blobs_path())
        if os.path.islink(shared_blobs_dir):
            raise core.CorruptedModelPackageError("Shared blob directory cannot be a symlink.")
        for declaration in declarations:
            package_path = os.path.join(package_dir, declaration["file_handle"])
            if not Path(os.path.abspath(package_path)).is_relative_to(Path(os.path.abspath(package_dir))):
                raise core.CorruptedModelPackageError("Artifact path escapes model package.")
            md5_hash = declaration["md5_hash"]
            if declaration["storage"] == "shared_blob":
                expected_blob = os.path.join(shared_blobs_dir, md5_hash)
                if os.path.islink(expected_blob) or not os.path.isfile(expected_blob) or core._md5_file(path=expected_blob) != md5_hash:
                    raise core.CorruptedModelPackageError(f"Expected blob {expected_blob} is missing or corrupted.")
                if os.path.islink(package_path) and os.path.realpath(package_path) != os.path.realpath(expected_blob):
                    raise core.CorruptedModelPackageError("Artifact symlink points outside the verified blob.")
                if not os.path.exists(package_path) or core._md5_file(path=package_path) != md5_hash:
                    shutil.copyfile(expected_blob, package_path)
                if core._md5_file(path=package_path) != md5_hash:
                    raise core.CorruptedModelPackageError("Copied artifact checksum mismatch.")
                identities.append({**declaration, "sha256_hash": None})
            else:
                if os.path.islink(package_path) or not os.path.isfile(package_path) or (md5_hash and core._md5_file(path=package_path) != md5_hash):
                    raise core.CorruptedModelPackageError(f"Package artifact {package_path} is invalid.")
                identities.append({**declaration, "sha256_hash": core._sha256_file(path=package_path) if not md5_hash else None})
        return identities

    core.handle_symlink_creation = safe_handle_symlink_creation
    core._materialize_package_artifact_identities = safe_materialize


def select_videos(source, names=None, data_dir=ROOT / "data"):
    videos = sorted(source.glob("*.mp4"))
    if names:
        if any(Path(name).name != name for name in names):
            raise ValueError("Use video basenames only")
        videos = [video for video in videos if video.name in names]
        if {v.name for v in videos} != set(names):
            raise ValueError("Requested video missing")
    # Smoke/demo runs must not consume the locked scoring holdout by default.
    split_path = data_dir / "splits.json"
    manifest_path = data_dir / "manifest.csv"
    if split_path.is_file() and manifest_path.is_file():
        import csv
        split = json.loads(split_path.read_text(encoding="utf-8"))
        if split.get("status") == "locked":
            test_ids = set(split["proposed_split"]["test"]["video_ids"])
            with manifest_path.open(newline="", encoding="utf-8") as handle:
                reserved = {(data_dir.parent / row["relative_path"]).resolve() for row in csv.DictReader(handle)
                            if row["video_id"] in test_ids}
            if names and any(video.resolve() in reserved for video in videos):
                raise ValueError("Requested video belongs to locked test split; use calibration for smoke tests")
            videos = [video for video in videos if video.resolve() not in reserved]
    if not videos:
        raise ValueError("No non-holdout MP4 files selected")
    return videos


def smoke(args, api_key):
    # Constrain cache and backend before importing the runtime; no video upload path.
    with private_library_output():
        import cv2
        from inference_models import AutoModel
        _apply_windows_symlink_compat()

    videos = select_videos(args.source, args.video_name)
    if args.output.resolve() == args.source.resolve() or args.output.resolve().is_relative_to(args.source.resolve()):
        raise ValueError("Output must be outside source directory")
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    with private_library_output():
        model = AutoModel.from_pretrained(
            MODEL_ID, api_key=api_key, backend="onnx", device="cpu",
            onnx_execution_providers=["CPUExecutionProvider"],
            allow_untrusted_packages=False, allow_local_code_packages=False,
            verify_hash_while_download=True, download_files_without_hash=False,
            trt_engine_host_code_allowed=False, verbose=False,
        )
    init_s = time.perf_counter() - start
    classes = list(model.class_names)
    if set(classes) != EXPECTED_CLASSES or len(classes) != 3:
        raise ValueError("Model class metadata differs from ball/rim/human")
    if "yolo26" not in type(model).__name__.lower():
        raise ValueError("Runtime did not load a YOLO26 model")
    report = {"status": "running", "model_id": MODEL_ID, "runtime_class": type(model).__name__,
              "backend": "onnx", "device": "cpu", "class_mapping": dict(enumerate(classes)),
              "created_utc": datetime.now(timezone.utc).isoformat(), "model_init_s": init_s,
              "confidence_threshold": args.confidence, "max_edge": args.max_edge,
              "versions": {name: importlib.metadata.version(name) for name in
                           ("inference-models", "opencv-python", "onnxruntime", "torch")},
              "warmup_ms": [], "samples": []}
    observed = set()
    for clip_index, video in enumerate(videos, 1):
        capture = cv2.VideoCapture(str(video.resolve()))
        try:
            if not capture.isOpened():
                raise ValueError("Cannot open video")
            fps = capture.get(cv2.CAP_PROP_FPS)
            count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if not math.isfinite(fps) or fps <= 0 or count <= 0:
                raise ValueError("Invalid video FPS/frame count")
            for sample_index in range(args.samples):
                frame_index = min(count - 1, int(count * (sample_index + 0.5) / args.samples))
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = capture.read()
                if not ok:
                    raise ValueError("Cannot decode requested frame")
                height, width = frame.shape[:2]
                scale = min(1, args.max_edge / max(width, height))
                image = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
                if not report["samples"]:
                    for _ in range(2):
                        start = time.perf_counter()
                        with private_library_output():
                            model(image)
                        report["warmup_ms"].append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                with private_library_output():
                    predictions = model(image)
                elapsed_ms = (time.perf_counter() - start) * 1000
                if len(predictions) != 1:
                    raise ValueError("Expected one output per image")
                detections = predictions[0].to_supervision()
                records = normalize_detections(detections.xyxy, detections.class_id, detections.confidence,
                                               classes, (width, height), (image.shape[1], image.shape[0]), args.confidence)
                for record in records:
                    observed.add(record["class_name"])
                    x1, y1, x2, y2 = record["xyxy"]
                    x1, x2 = round(x1 * image.shape[1] / width), round(x2 * image.shape[1] / width)
                    y1, y2 = round(y1 * image.shape[0] / height), round(y2 * image.shape[0] / height)
                    color = {"ball": (0, 200, 255), "rim": (255, 180, 0), "human": (0, 220, 0)}[record["class_name"]]
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(image, f"{record['class_name']} {record['confidence']:.2f}",
                                (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                filename = f"clip{clip_index:02d}_frame{frame_index:05d}.jpg"
                if not cv2.imwrite(str((args.output / filename).resolve()), image):
                    raise OSError("Cannot write annotated image")
                report["samples"].append({"video": video.name, "frame_index": frame_index,
                                           "source_time_s": frame_index / fps,
                                           "original_wh": [width, height],
                                           "input_wh": [image.shape[1], image.shape[0]],
                                           "model_call_ms": elapsed_ms, "detections": records, "overlay": filename})
        finally:
            capture.release()
    times = [sample["model_call_ms"] for sample in report["samples"]]
    report.update({"status": "completed", "observed_classes": sorted(observed),
                   "unobserved_classes": sorted(EXPECTED_CLASSES - observed),
                   "model_call_median_ms": statistics.median(times), "model_call_mean_ms": statistics.mean(times),
                   "timing_scope": "CPU model call including preprocessing/postprocessing; excludes decode, external resize and drawing. Not end-to-end FPS."})
    (args.output / "smoke.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Completed {len(times)} samples. Model call median: {statistics.median(times):.1f} ms. See smoke.json and overlays.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "assets_test")
    parser.add_argument("--video-name", action="append", help="Select local video basename; repeat to select multiple non-holdout clips")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / ("smoke-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--check-credentials", action="store_true", help="Validate config only; no imports/download/inference")
    parser.add_argument("--samples", type=int, default=6, help="Frames per video (1–30); smoke test, not event evaluation")
    parser.add_argument("--max-edge", type=int, default=1280)
    parser.add_argument("--confidence", type=float, default=0.25)
    args = parser.parse_args()
    if not 1 <= args.samples <= 30 or not 320 <= args.max_edge <= 4096 or not 0 < args.confidence <= 1:
        parser.error("Invalid sample count, max edge or confidence")
    try:
        key = load_credentials(args.env_file)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + "\n")
    if args.check_credentials:
        print("Credential configured; approved model ID matched. Key not displayed. Remote validity not tested.")
        return
    try:
        smoke(args, key)
    except Exception as error:
        # Do not echo secret strings/tracebacks: upstream URLs may embed API keys.
        causes = ""
        if getattr(error, "alternatives_errors", None):
            causes = ": " + ", ".join(type(item).__name__ for item in error.alternatives_errors)
        parser.exit(3, f"Smoke test stopped ({type(error).__name__}{causes}). No success report. Review runtime/access/schema before retrying.\n")


if __name__ == "__main__":
    main()
