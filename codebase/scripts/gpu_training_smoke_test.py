#!/usr/bin/env python3
"""Execute real forward, detection loss, backward, and optimizer smoke test on GPU.

Verifies:
- torch and torchvision CUDA compatibility on RTX 2050
- Forward pass with AMP autocast and real YOLO detection criterion (loss uses labels)
- Label sensitivity (changing labels changes loss)
- Backward gradient propagation (finite and non-zero)
- Optimizer step with actual weight update in memory
- VRAM footprint on 4GB hardware
- Does NOT save weights or corrupt checkpoint
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = ROOT / "models/checkpoints/task07a-original/best.pt"
DEFAULT_OUTPUT_PATH = ROOT / "outputs/task07a-finetune-20261108/gpu-training-smoke.json"


def run_smoke(output_path: Path | str = DEFAULT_OUTPUT_PATH):
    import torch
    import torchvision
    import ultralytics
    from ultralytics import YOLO
    from ultralytics.cfg import DEFAULT_CFG_DICT, get_cfg

    output_file = Path(output_path).resolve()
    t0 = time.perf_counter()
    report = {
        "status": "starting",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "ultralytics_version": ultralytics.__version__,
        "cuda_available": torch.cuda.is_available(),
    }

    if not torch.cuda.is_available():
        report["status"] = "failed_cuda_unavailable"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError("CUDA is not available in current environment")

    device_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    total_vram_mb = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)

    report["device"] = {
        "index": 0,
        "name": device_name,
        "capability": capability,
        "total_vram_mb": round(total_vram_mb, 2),
    }

    print(f"Loading checkpoint: {CHECKPOINT_PATH}")
    yolo_wrapper = YOLO(str(CHECKPOINT_PATH))
    nn_model = yolo_wrapper.model.to("cuda:0")
    nn_model.train()  # Switch to training mode

    # Ensure full training hyperparameters are attached for the criterion
    nn_model.args = get_cfg(DEFAULT_CFG_DICT, overrides=nn_model.args)

    for p in nn_model.parameters():
        p.requires_grad = True

    param_count = sum(p.numel() for p in nn_model.parameters())
    trainable_count = sum(p.numel() for p in nn_model.parameters() if p.requires_grad)
    report["model"] = {
        "task": yolo_wrapper.task,
        "parameters_total": param_count,
        "parameters_trainable": trainable_count,
    }

    # Setup AdamW optimizer
    optimizer = torch.optim.AdamW(
        [p for p in nn_model.parameters() if p.requires_grad],
        lr=0.0001,
        weight_decay=0.0005,
    )

    # Synthetic batch: batch_size=2, 3 channels, 640x640
    batch_size = 2
    imgsz = 640
    dummy_imgs = torch.rand((batch_size, 3, imgsz, imgsz), device="cuda:0", dtype=torch.float32)

    # Batch dict matching Ultralytics detection loss expectations
    batch_dict = {
        "img": dummy_imgs,
        "batch_idx": torch.tensor([0, 0, 1, 1], device="cuda:0", dtype=torch.int64),
        "cls": torch.tensor([[0.0], [1.0], [1.0], [2.0]], device="cuda:0", dtype=torch.float32),
        "bboxes": torch.tensor([
            [0.5, 0.5, 0.1, 0.1],
            [0.3, 0.4, 0.2, 0.5],
            [0.7, 0.6, 0.15, 0.4],
            [0.5, 0.2, 0.1, 0.08],
        ], device="cuda:0", dtype=torch.float32),
    }

    torch.cuda.reset_peak_memory_stats(0)
    torch.cuda.empty_cache()

    scaler = torch.amp.GradScaler("cuda", init_scale=128.0)

    print("Running forward pass with AMP autocast and detection criterion...")
    with torch.amp.autocast("cuda", enabled=True):
        loss_tensor, loss_dict = nn_model(batch_dict)
        loss = loss_tensor.sum()
        loss_items = [loss_tensor[i].detach() for i in range(len(loss_tensor))]

    print(f"Forward completed. Loss: {loss.item():.4f}, components: {loss_dict}")
    if not torch.isfinite(loss):
        raise ValueError(f"Non-finite loss computed: {loss}")

    # Verify label sensitivity: changing target labels must alter the loss
    batch_alt = {k: v.clone() if isinstance(v, torch.Tensor) else v for k, v in batch_dict.items()}
    batch_alt["bboxes"] = torch.clamp(batch_alt["bboxes"] + 0.15, 0.0, 1.0)
    with torch.amp.autocast("cuda", enabled=True):
        loss_alt_tensor, _ = nn_model(batch_alt)
        loss_alt = loss_alt_tensor.sum()
    loss_delta = abs(loss.item() - loss_alt.item())
    if loss_delta < 1e-4:
        raise ValueError(f"Detection loss did not respond to label perturbation: delta={loss_delta}")

    # Track weights before optimizer step
    p_before = [p.clone() for p in nn_model.parameters() if p.requires_grad][:5]

    print("Running backward pass via GradScaler...")
    optimizer.zero_grad(set_to_none=True)
    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)

    # Check that gradients were populated on parameters
    grads_present = sum(1 for p in nn_model.parameters() if p.grad is not None)
    finite_gradients = all(torch.isfinite(p.grad).all().item() for p in nn_model.parameters() if p.grad is not None)
    nonzero_gradients = any((p.grad.abs() > 0).any().item() for p in nn_model.parameters() if p.grad is not None)

    if grads_present == 0:
        raise ValueError("No gradients computed in backward pass")
    if not finite_gradients:
        raise ValueError("Non-finite gradients detected")
    if not nonzero_gradients:
        raise ValueError("All gradients were zero")
    print(f"Gradients computed on {grads_present} parameter tensors (finite={finite_gradients}, nonzero={nonzero_gradients}).")

    print("Running optimizer step...")
    scaler.step(optimizer)
    scaler.update()

    torch.cuda.synchronize()

    # Verify actual weight updates
    p_after = [p.clone() for p in nn_model.parameters() if p.requires_grad][:5]
    max_weight_diff = max((a - b).abs().max().item() for a, b in zip(p_after, p_before))
    if max_weight_diff <= 0.0:
        raise ValueError("Optimizer step did not update parameter weights in memory")
    print(f"Optimizer step verified: max weight diff = {max_weight_diff:.6e}")

    elapsed_s = time.perf_counter() - t0
    peak_vram_mb = torch.cuda.max_memory_allocated(0) / (1024 * 1024)
    reserved_vram_mb = torch.cuda.memory_reserved(0) / (1024 * 1024)

    report.update({
        "status": "gpu_training_smoke_passed",
        "batch_size": batch_size,
        "imgsz": imgsz,
        "amp_autocast": True,
        "loss_value": round(float(loss.item()), 4),
        "loss_components": {k: round(float(v.detach().cpu().item()), 4) for k, v in loss_dict.items()},
        "label_sensitivity_delta": round(float(loss_delta), 4),
        "gradients_computed_tensors": grads_present,
        "finite_gradients": finite_gradients,
        "nonzero_gradients": nonzero_gradients,
        "optimizer_step_executed": True,
        "weight_updated_in_memory": True,
        "max_parameter_weight_diff": max_weight_diff,
        "peak_vram_allocated_mb": round(peak_vram_mb, 2),
        "vram_reserved_mb": round(reserved_vram_mb, 2),
        "vram_headroom_mb": round(total_vram_mb - reserved_vram_mb, 2),
        "elapsed_seconds": round(elapsed_s, 2),
    })

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n=== GPU TRAINING SMOKE TEST PASSED ===")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    args = parser.parse_args()
    run_smoke(args.output)
