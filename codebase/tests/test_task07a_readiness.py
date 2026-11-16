"""Test training readiness, hyperparameter resolution, and download completion."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

SPEC_READY = importlib.util.spec_from_file_location("prepare_task07a_ready", SCRIPTS / "prepare_task07a_ready.py")
ready_module = importlib.util.module_from_spec(SPEC_READY)
SPEC_READY.loader.exec_module(ready_module)

SPEC_PROBE = importlib.util.spec_from_file_location("probe_task07a_gpu_training", SCRIPTS / "probe_task07a_gpu_training.py")
probe_module = importlib.util.module_from_spec(SPEC_PROBE)
SPEC_PROBE.loader.exec_module(probe_module)


def test_complete_progress_waits_for_both_wheel_manifest_rows(tmp_path):
    stages = {name: dict(status="completed") for name in ("dataset", "torchvision", "torch")}
    manifest = tmp_path / "manifest.json"
    assert not ready_module.downloads_complete(stages, manifest)
    manifest.write_text(json.dumps([dict(package="torchvision")]))
    assert not ready_module.downloads_complete(stages, manifest)
    manifest.write_text(json.dumps([dict(package="torchvision"), dict(package="torch")]))
    assert ready_module.downloads_complete(stages, manifest)


def test_manifest_cannot_hide_an_incomplete_download(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([dict(package="torchvision"), dict(package="torch")]))
    stages = dict(dataset=dict(status="downloading"), torch=dict(status="completed"), torchvision=dict(status="completed"))
    assert not ready_module.downloads_complete(stages, manifest)


def test_detection_loss_hyperparameters_resolved():
    """Verify that model.args configured via DEFAULT_CFG_DICT contains box, cls, dfl gains."""
    try:
        from ultralytics.cfg import DEFAULT_CFG_DICT, get_cfg
    except ImportError:
        pytest.skip("Ultralytics not installed in this environment")

    base_args = {"task": "detect", "data": "data.yaml", "imgsz": 640}
    cfg = get_cfg(DEFAULT_CFG_DICT, overrides=base_args)
    assert hasattr(cfg, "box"), "Config must include 'box' hyperparameter for BboxLoss"
    assert hasattr(cfg, "cls"), "Config must include 'cls' hyperparameter"
    assert hasattr(cfg, "dfl"), "Config must include 'dfl' hyperparameter"
    assert cfg.box > 0
    assert cfg.cls > 0


def test_probe_raises_on_checkpoint_tampering(tmp_path):
    """Verify that probe detects if the checkpoint file is tampered with."""
    try:
        import torch
    except ImportError:
        pytest.skip("PyTorch not installed")

    fake_ckpt = tmp_path / "fake.pt"
    fake_ckpt.write_bytes(b"not-a-valid-checkpoint")
    with pytest.raises(Exception):
        probe_module.run_probe(str(fake_ckpt), str(tmp_path / "out.json"))
