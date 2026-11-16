"""Read-only environment probe. Never reads or prints API keys."""
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
from pathlib import Path


def collect():
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "logical_cpus": os.cpu_count(),
        "recommended_runtime_python": "3.12",
        "packages": {},
    }
    for package in ("opencv-python", "inference-models", "torch", "onnxruntime", "onnxruntime-gpu"):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = None
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        result["gpu"] = gpu.stdout.strip() if gpu.returncode == 0 else "query failed"
    except (OSError, subprocess.TimeoutExpired):
        result["gpu"] = "unavailable"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(collect(), indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
