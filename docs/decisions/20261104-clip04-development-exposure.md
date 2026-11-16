# Clip04 dùng cho development Task07 — quyết định 2026-11-04

Người dùng yêu cầu chạy một video trận 3x3 trong `assets_test` với roster giả lập, sau đó xác nhận: **“Đồng ý dùng clip04 và ghi nhận exposure của nhóm cùng trận.”**

- Clip được phép chạy: `2aOboR9Z2NjQ1XP8HgYdKMG7VVzS44zOdTVVjB5s.mp4`, SHA-256 `ae789418b89cfcf868a546eb0a5ce502497bb6d2b61af252978038d7cf8af3c4`.
- Phạm vi: development/demo Task07, roster giả lập; không dùng nhãn sự kiện hoặc notes làm đầu vào recognition.
- Exposure áp dụng cho **nhóm clip04–07 cùng trận/nguồn**. Không tiếp tục gọi nhóm này là holdout độc lập chưa tiếp xúc trong các đánh giá mới. Điều này không khẳng định đã chạy inference trên clip05–07.
- Giữ nguyên manifest, annotations, splits và lock v1. Kết quả nghiệm thu lịch sử vẫn là lịch sử; đánh giá tổng quát mới cần nhóm test khác chưa dùng development.
- [Authorization JSON](../../codebase/configs/development_authorizations/task07-clip04.json) lưu source SHA, phạm vi, xác nhận người dùng và toàn bộ hashes nhóm đã exposure.

CLI mặc định tiếp tục từ chối các hashes holdout. Chỉ truyền `--development-authorization codebase/configs/development_authorizations/task07-clip04.json` mới cho chạy đúng clip04. Quyền này không mở clip05–07; tests kiểm tra cả default-deny, đúng hash và thiếu exposure của nhóm. File authorization là bản ghi quyết định trong workspace, không phải cơ chế chữ ký xác thực danh tính người duyệt.

Authorization được ghi vào metadata detection/tracking/task07. Các lời nhắc “clip04–07 luôn chưa được dùng development” trong tài liệu cũ cần đọc cùng quyết định mới này.
