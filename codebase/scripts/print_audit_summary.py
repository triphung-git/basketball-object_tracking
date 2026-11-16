import json
from pathlib import Path

p = Path("codebase/outputs/task07a-finetune-20261108/original_dataset_label_audit.json")
data = json.loads(p.read_text(encoding="utf-8"))
errs = data["errors"]

print(f"Total out-of-bounds errors: {len(errs)}")
max_px = max(e["max_oob_px"] for e in errs)
min_px = min(e["max_oob_px"] for e in errs)
max_norm = max(e["max_oob_norm"] for e in errs)
min_norm = min(e["max_oob_norm"] for e in errs)
print(f"OOB Pixel range: [{min_px}, {max_px}] px")
print(f"OOB Normalized range: [{min_norm}, {max_norm}]")

for i, e in enumerate(errs, 1):
    print(f"{i:2d}. {e['split']} | {e['class']:5s} | max_oob_px: {e['max_oob_px']:4.1f}px | max_oob_norm: {e['max_oob_norm']:.6f} | img: {e['image']}")
