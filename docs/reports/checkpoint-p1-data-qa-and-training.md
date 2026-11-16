# Checkpoint Ưu tiên 1 — Khôi Phục Data QA và Khởi Động Huấn Luyện Candidate Task07

**Ngày thực hiện:** 2026-11-09  
**Trạng thái Ưu tiên 1:** IMPLEMENTED, EXECUTED, MEASURED, AND ACTIVE ON GPU  

---

## 1. Kết Quả Audit Toàn Bộ Nhãn Bounding Box Gốc (1A)

- **Tổng số ảnh kiểm kê:** 9,515 ảnh (train: 6,662; valid: 1,893; test: 960).
- **Tổng số nhãn bounding box:** 36,988 boxes (rim: 6,744; ball: 9,597; human: 20,647).
- **Phân loại lỗi nhãn:**
  - Nhãn thiếu file (missing label): **0**.
  - Tọa độ không xác định (nonfinite): **0**.
  - Diện tích rỗng (zero area): **0**.
  - Sai lệch class mapping: **0**.
  - Lỗi vượt biên nghiêm trọng (> 0.05 normalized / > 32px): **0**.
  - Sai số lượng tử hóa biên (0.5px border quantization): **24 bounding boxes** thuộc 19 ảnh (train: 21 boxes / 16 ảnh; valid: 1 box / 1 ảnh; test: 2 boxes / 2 ảnh; ball: 1 box; human: 23 boxes).
- **Đo lường sai số:** Mọi box bị vượt biên đều vượt đúng $0.5\text{px}$ (normalized: $0.000375$ đến $0.002732$), do việc làm tròn tọa độ nguyên sang float trong bản xuất Roboflow.
- **Bảo toàn dữ liệu gốc:** Thư mục gốc `codebase/data/finetune/task07a/original/export` được giữ nguyên 100%, không bị sửa đổi hay ghi đè.
- **Bản xuất dẫn xuất có version (Derived Dataset Export v1):**
  - Đã tạo `codebase/data/finetune/task07a/derived_export_v1/`.
  - Áp dụng chính sách hình học giao với miền ảnh đơn vị $[0.0, 1.0]$:
    $$x_1 = \max(0.0, \min(1.0, c_x - w/2)), \quad x_2 = \max(0.0, \min(1.0, c_x + w/2))$$
    $$y_1 = \max(0.0, \min(1.0, c_y - h/2)), \quad y_2 = \max(0.0, \min(1.0, c_y + h/2))$$
  - Ghi nhận chi tiết toàn bộ trước/sau tọa độ và SHA-256 tại [`codebase/data/finetune/task07a/derived_export_v1/repair_manifest.json`](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/data/finetune/task07a/derived_export_v1/repair_manifest.json).
  - 100% 9,515 nhãn trong bản xuất dẫn xuất đã qua kiểm thử `validate_yolo_strict` với ngưỡng dung sai $10^{-6}$.

---

## 2. Kết Quả GPU Smoke Test & Preflight (1B)

- **Môi trường `.venv-train`:**
  - PyTorch: `2.11.0+cu128` (CUDA available = True).
  - Torchvision: `0.26.0+cu128`.
  - Ultralytics: `8.4.207`.
  - Phần cứng: `NVIDIA GeForce RTX 2050` (Compute Capability 8.6, 4095.56 MB VRAM).
- **GPU Smoke Test thực tế:** Đã chạy qua forward AMP autocast, dual-head loss (`one2many` + `one2one`), backward qua GradScaler trên 366 parameter tensors, và optimizer step với AdamW.
  - VRAM cấp phát đỉnh (peak VRAM): $599.77\text{ MB}$.
  - VRAM dự trữ: $694.00\text{ MB}$.
  - VRAM khả dụng còn lại: $3,401.56\text{ MB}$ (đủ an toàn cho batch 2, imgsz 640).
  - Báo cáo chi tiết: [`codebase/outputs/task07a-finetune-20261108/gpu-training-smoke.json`](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/outputs/task07a-finetune-20261108/gpu-training-smoke.json).

---

## 3. Mixed Dataset & Khởi Động Huấn Luyện Candidate

- **Mixed Dataset:** `codebase/data/finetune/task07a/mixed-20261108`
  - Train: 6,711 ảnh (6,662 original + 49 supplemental rows đã duyệt).
  - Valid: 515 ảnh (quarantine toàn bộ holdout cùng source family hoặc exact pixel hash với train).
  - Test: 219 ảnh (quarantine toàn bộ holdout trùng với train/valid).
  - Loại bỏ hoàn toàn 308 hàng nhãn draft chưa duyệt.
- **Preflight:** `status: preflight_passed`, lưu tại [`codebase/outputs/task07a-candidate-20261109/run.json`](file:///c:/Users/Admin/OneDrive%20-%20National%20Economics%20University/Documents/object%20tracking/codebase/outputs/task07a-candidate-20261109/run.json).
- **Tiến trình huấn luyện:** Đang chạy trên GPU RTX 2050 (PID đang theo dõi trong task runner, 30 epochs, batch 2, imgsz 640, AdamW, seed 7).
