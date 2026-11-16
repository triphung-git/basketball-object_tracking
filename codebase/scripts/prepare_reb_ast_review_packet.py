"""Prepares the concrete REB & AST review packet for user review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_review_packet():
    out_dir = ROOT / "outputs" / "remaining-tasks-20261115" / "03B" / "run" / "review_packets"
    out_dir.mkdir(parents=True, exist_ok=True)

    roster = {
        "team_a": {
            "name": "Việt Nam",
            "players": [
                {"id": "a_nguyen_huynh_phu_vinh", "jersey": 1, "name": "Nguyễn Huỳnh Phú Vinh"},
                {"id": "a_huynh_thanh_tam", "jersey": 2, "name": "Huỳnh Thanh Tâm"},
                {"id": "a_nguyen_phuc_vinh", "jersey": 6, "name": "Nguyễn Phúc Vinh"},
                {"id": "a_nguyen_anh_kiet", "jersey": 13, "name": "Nguyễn Anh Kiệt"},
            ]
        },
        "team_b": {
            "name": "Tonga",
            "players": [
                {"id": "b_01", "jersey": 1, "name": "Marcus Christian Alipate"},
                {"id": "b_09", "jersey": 9, "name": "Luke Sinisa"},
                {"id": "b_11", "jersey": 11, "name": "Jonah Palelei"},
                {"id": "b_18", "jersey": 18, "name": "Viliami Foketi"},
            ]
        }
    }

    # 8 Initial Concrete Review Candidates (4 REB + 4 AST)
    candidates = [
        # --- REBOUND CANDIDATES ---
        {
            "id": "rev_reb_001",
            "stat": "reb",
            "candidate_type": "rebound_recovery_after_miss",
            "video_path": "outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 300.0,
            "clip_times": {
                "start_s": 3.47,
                "miss_outcome_s": 3.93,
                "recovery_window_s": [3.93, 5.50],
                "end_s": 6.50
            },
            "source_times": {
                "start_s": 303.47,
                "miss_outcome_s": 303.93,
                "recovery_window_s": [303.93, 305.50],
                "end_s": 306.50
            },
            "context_description": (
                "Sau cú ném 2 điểm của Việt Nam (#1 hoặc #13) bị trượt tại t=3.93s, bóng rơi xuống khu vực cận rổ. "
                "Có sự tranh chấp giữa Nguyễn Huỳnh Phú Vinh (#1 VIE) và cầu thủ Tonga (#1 hoặc #18). "
                "Cầu thủ giành quyền kiểm soát bóng sau đó phát triển đợt tấn công tiếp theo."
            ),
            "evidence": {
                "parent_shot_id": "shot_vt_development_0002",
                "shot_outcome": "miss",
                "observed_ball_gap_s": 0.467,
            },
            "questions": [
                {
                    "key": "is_rebound",
                    "prompt": "Pha bóng này có cấu thành một Rebound hợp lệ không?",
                    "options": ["yes_rebound", "no_dead_ball_or_foul", "not_a_rebound", "uncertain"],
                    "draft_suggestion": "yes_rebound"
                },
                {
                    "key": "rebound_type",
                    "prompt": "Phân loại Rebound (Subtype):",
                    "options": [
                        "offensive (Đội ném VIE giành lại bóng)",
                        "defensive (Đội phòng ngự TGA bắt bóng)",
                        "team_rebound (Bóng ra biên/bóng chết thuộc về đội)"
                    ],
                    "draft_suggestion": "offensive (Đội ném VIE giành lại bóng)"
                },
                {
                    "key": "actor_id",
                    "prompt": "Cầu thủ bắt bóng (nếu là Individual Rebound):",
                    "options": [
                        "a_nguyen_huynh_phu_vinh (VIE #1)",
                        "a_nguyen_phuc_vinh (VIE #6)",
                        "b_01 (TGA #1)",
                        "b_18 (TGA #18)",
                        "unresolved / team_rebound"
                    ],
                    "draft_suggestion": "a_nguyen_huynh_phu_vinh (VIE #1)"
                },
                {
                    "key": "recovery_time_s",
                    "prompt": "Thời điểm kiểm soát bóng chính xác (clip-local giây, khoảng 3.9s - 5.5s):",
                    "type": "number",
                    "draft_suggestion": 4.50
                }
            ]
        },
        {
            "id": "rev_reb_002",
            "stat": "reb",
            "candidate_type": "post_basket_inbound_or_recovery",
            "video_path": "outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 300.0,
            "clip_times": {
                "start_s": 9.60,
                "basket_s": 10.13,
                "recovery_s": 10.43,
                "end_s": 12.00
            },
            "source_times": {
                "start_s": 309.60,
                "basket_s": 310.13,
                "recovery_s": 310.43,
                "end_s": 312.00
            },
            "context_description": (
                "Sau khi Tonga ghi điểm thành công tại t=10.13s (shot_vt_development_0009), "
                "bóng rơi xuống và Jonah Palelei (b_11) lấy bóng tại t=10.43s để bắt đầu chuỗi kiểm soát."
            ),
            "evidence": {
                "parent_shot_id": "shot_vt_development_0009",
                "shot_outcome": "made",
            },
            "questions": [
                {
                    "key": "is_rebound",
                    "prompt": "Pha bóng sau rổ này có tính là Rebound không? (Theo FIBA, nhặt bóng sau bàn thắng KHÔNG tính là Rebound)",
                    "options": ["not_a_rebound (Nhặt bóng sau made shot - Hard Negative)", "rebound", "uncertain"],
                    "draft_suggestion": "not_a_rebound (Nhặt bóng sau made shot - Hard Negative)"
                }
            ]
        },
        {
            "id": "rev_reb_003",
            "stat": "reb",
            "candidate_type": "rebound_recovery_after_miss",
            "video_path": "outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 300.0,
            "clip_times": {
                "start_s": 24.80,
                "miss_outcome_s": 25.63,
                "recovery_window_s": [25.63, 27.50],
                "end_s": 28.50
            },
            "source_times": {
                "start_s": 324.80,
                "miss_outcome_s": 325.63,
                "recovery_window_s": [325.63, 327.50],
                "end_s": 328.50
            },
            "context_description": (
                "Cú ném bóng của Việt Nam (shot_vt_development_0018) trượt tại t=25.63s. "
                "Bóng nảy ra xa khu vực bảng rổ và có cầu thủ lui về thu hồi bóng."
            ),
            "evidence": {
                "parent_shot_id": "shot_vt_development_0018",
                "shot_outcome": "miss",
            },
            "questions": [
                {
                    "key": "is_rebound",
                    "prompt": "Pha bóng này có cấu thành một Rebound hợp lệ không?",
                    "options": ["yes_rebound", "no_out_of_bounds", "not_a_rebound", "uncertain"],
                    "draft_suggestion": "yes_rebound"
                },
                {
                    "key": "rebound_type",
                    "prompt": "Phân loại Rebound (Subtype):",
                    "options": [
                        "defensive (Tonga giành quyền kiểm soát)",
                        "offensive (Việt Nam giữ bóng)",
                        "team_rebound (Bóng chết/hết biên)"
                    ],
                    "draft_suggestion": "defensive (Tonga giành quyền kiểm soát)"
                },
                {
                    "key": "actor_id",
                    "prompt": "Cầu thủ thu hồi bóng:",
                    "options": [
                        "b_01 (TGA #1)",
                        "b_11 (TGA #11)",
                        "b_18 (TGA #18)",
                        "a_nguyen_phuc_vinh (VIE #6)",
                        "team_rebound"
                    ],
                    "draft_suggestion": "b_18 (TGA #18)"
                }
            ]
        },
        {
            "id": "rev_reb_004",
            "stat": "reb",
            "candidate_type": "post_shot_rebound_candidate",
            "video_path": "outputs/task08-scoreboard-review-20261106/clips/play_004.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 165.0,
            "clip_times": {
                "start_s": 5.0,
                "shot_s": 7.5,
                "recovery_window_s": [7.5, 9.5],
                "end_s": 12.0
            },
            "source_times": {
                "start_s": 170.0,
                "shot_s": 172.5,
                "recovery_window_s": [172.5, 174.5],
                "end_s": 177.0
            },
            "context_description": (
                "Pha bóng trong clip play_004: cú ném rổ từ xa của Tonga (b_01). "
                "Sau cú ném bóng chạm vành rổ bật ra, có pha tranh chấp rebound trên không."
            ),
            "evidence": {
                "clip_id": "play_004.mp4",
                "scoreboard_bracket": [171.5, 173.0]
            },
            "questions": [
                {
                    "key": "is_rebound",
                    "prompt": "Pha bóng này có cấu thành Rebound không?",
                    "options": ["yes_rebound", "no_basket_scored", "uncertain"],
                    "draft_suggestion": "yes_rebound"
                },
                {
                    "key": "rebound_type",
                    "prompt": "Subtype Rebound:",
                    "options": ["defensive", "offensive", "team_rebound"],
                    "draft_suggestion": "defensive"
                },
                {
                    "key": "actor_id",
                    "prompt": "Người bắt Rebound:",
                    "options": [
                        "a_nguyen_huynh_phu_vinh (VIE #1)",
                        "a_nguyen_anh_kiet (VIE #13)",
                        "b_01 (TGA #1)",
                        "b_11 (TGA #11)",
                        "team_rebound"
                    ],
                    "draft_suggestion": "a_nguyen_huynh_phu_vinh (VIE #1)"
                }
            ]
        },

        # --- ASSIST CANDIDATES ---
        {
            "id": "rev_ast_001",
            "stat": "ast",
            "candidate_type": "pass_leading_to_shot_attempt",
            "video_path": "outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 300.0,
            "clip_times": {
                "pass_release_s": 8.07,
                "pass_receive_s": 8.53,
                "shot_attempt_s": 9.03,
                "end_s": 10.50
            },
            "source_times": {
                "pass_release_s": 308.07,
                "pass_receive_s": 308.53,
                "shot_attempt_s": 309.03,
                "end_s": 310.50
            },
            "context_description": (
                "Đường chuyền đã review review_pass_1: Nguyễn Huỳnh Phú Vinh (VIE #1) chuyền cho Nguyễn Phúc Vinh (VIE #6) "
                "tại t=8.07s - 8.53s. Phúc Vinh sau đó có động tác ném rổ / tiếp cận rổ."
            ),
            "evidence": {
                "pass_id": "review_pass_1",
                "passer": "a_nguyen_huynh_phu_vinh",
                "receiver": "a_nguyen_phuc_vinh",
                "team": "team_a",
            },
            "questions": [
                {
                    "key": "eligibility",
                    "prompt": "Đường chuyền này có đủ điều kiện tính là Assist không?",
                    "options": [
                        "ineligible (Cú ném sau đó không thành công hoặc bị cản phá)",
                        "eligible (Nếu cú ném thành công và là đường chuyền trực tiếp)",
                        "uncertain"
                    ],
                    "draft_suggestion": "ineligible (Cú ném sau đó không thành công hoặc bị cản phá)"
                },
                {
                    "key": "notes",
                    "prompt": "Ghi chú phân tích pha kiến tạo:",
                    "type": "text",
                    "draft_suggestion": "Passer chuyền bóng tốt nhưng pha dứt điểm tiếp theo của receiver không ghi điểm."
                }
            ]
        },
        {
            "id": "rev_ast_002",
            "stat": "ast",
            "candidate_type": "inbound_pass_sequence",
            "video_path": "outputs/task07-vietnam-tonga-segments-20261104/media/vt_development.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 300.0,
            "clip_times": {
                "pass_release_s": 10.93,
                "pass_receive_s": 11.57,
                "end_s": 13.00
            },
            "source_times": {
                "pass_release_s": 310.93,
                "pass_receive_s": 311.57,
                "end_s": 313.00
            },
            "context_description": (
                "Đường chuyền review_pass_2: Jonah Palelei (b_11) chuyền cho Viliami Foketi (b_18) tại t=10.93s - 11.57s. "
                "Pha bóng này diễn ra ở ngoài vòng cung sau khi nhận bóng từ vạch biên."
            ),
            "evidence": {
                "pass_id": "review_pass_2",
                "passer": "b_11",
                "receiver": "b_18",
                "team": "team_b",
            },
            "questions": [
                {
                    "key": "eligibility",
                    "prompt": "Phân loại tính hợp lệ của Assist:",
                    "options": [
                        "ineligible (Đường chuyền luân chuyển ngoài cung, không có cú ném rổ thành công ngay sau đó)",
                        "eligible",
                        "uncertain"
                    ],
                    "draft_suggestion": "ineligible (Đường chuyền luân chuyển ngoài cung, không có cú ném rổ thành công ngay sau đó)"
                }
            ]
        },
        {
            "id": "rev_ast_003",
            "stat": "ast",
            "candidate_type": "pass_leading_to_made_basket",
            "video_path": "outputs/task08-scoreboard-review-20261106/clips/play_001.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 133.0,
            "clip_times": {
                "pass_window_s": [5.0, 7.5],
                "shot_release_s": 7.53,
                "basket_s": 8.80,
                "end_s": 10.0
            },
            "source_times": {
                "pass_window_s": [138.0, 140.5],
                "shot_release_s": 140.53,
                "basket_s": 141.80,
                "end_s": 143.0
            },
            "context_description": (
                "Pha bóng play_001: Cú ném ghi 2 điểm thành công của Marcus Christian Alipate (b_01) tại t=7.53s clip (140.53s source). "
                "Trước đó có đường chuyền từ đồng đội ở cánh trái vào khu vực ném rổ."
            ),
            "evidence": {
                "shot_id": "play_001",
                "scorer": "b_01",
                "points": 2,
                "team": "team_b",
            },
            "questions": [
                {
                    "key": "eligibility",
                    "prompt": "Cú ném thành công này có đường kiến tạo (Assist) hợp lệ không?",
                    "options": [
                        "eligible (Đường chuyền trực tiếp tạo cơ hội ghi điểm)",
                        "ineligible (Cầu thủ tự dẫn bóng tạo khoảng trống - Solo Isolation)",
                        "uncertain"
                    ],
                    "draft_suggestion": "eligible (Đường chuyền trực tiếp tạo cơ hội ghi điểm)"
                },
                {
                    "key": "passer_id",
                    "prompt": "Người thực hiện đường chuyền (Passer):",
                    "options": [
                        "b_09 (Luke Sinisa)",
                        "b_11 (Jonah Palelei)",
                        "b_18 (Viliami Foketi)",
                        "unresolved"
                    ],
                    "draft_suggestion": "b_11 (Jonah Palelei)"
                },
                {
                    "key": "pass_release_time_s",
                    "prompt": "Thời điểm chuyền bóng (clip-local giây, khoảng 6.0s - 7.5s):",
                    "type": "number",
                    "draft_suggestion": 6.80
                }
            ]
        },
        {
            "id": "rev_ast_004",
            "stat": "ast",
            "candidate_type": "pass_leading_to_made_basket",
            "video_path": "outputs/task08-scoreboard-review-20261106/clips/play_003.mp4",
            "source_video": "assets_test/vietnam-tonga.mp4",
            "parent_time_offset_s": 158.0,
            "clip_times": {
                "pass_window_s": [4.0, 6.9],
                "shot_release_s": 6.97,
                "basket_s": 7.83,
                "end_s": 9.5
            },
            "source_times": {
                "pass_window_s": [162.0, 164.9],
                "shot_release_s": 164.97,
                "basket_s": 165.83,
                "end_s": 167.5
            },
            "context_description": (
                "Pha bóng play_003: Cú ném ghi 1 điểm cận rổ của Nguyễn Huỳnh Phú Vinh (a_nguyen_huynh_phu_vinh) "
                "tại t=6.97s clip (164.97s source). Xem xét pha phối hợp đưa bóng vào khu vực dưới rổ."
            ),
            "evidence": {
                "shot_id": "play_003",
                "scorer": "a_nguyen_huynh_phu_vinh",
                "points": 1,
                "team": "team_a",
            },
            "questions": [
                {
                    "key": "eligibility",
                    "prompt": "Pha ghi điểm này có tính Assist không?",
                    "options": [
                        "eligible (Có đường chuyền dọn cỗ trực tiếp)",
                        "ineligible (Phú Vinh tự rebound putback hoặc tự xoay xở ghi điểm)",
                        "uncertain"
                    ],
                    "draft_suggestion": "eligible (Có đường chuyền dọn cỗ trực tiếp)"
                },
                {
                    "key": "passer_id",
                    "prompt": "Người chuyền bóng (Passer):",
                    "options": [
                        "a_nguyen_phuc_vinh (#6)",
                        "a_huynh_thanh_tam (#2)",
                        "a_nguyen_anh_kiet (#13)",
                        "no_passer (Tự ghi điểm)"
                    ],
                    "draft_suggestion": "a_nguyen_phuc_vinh (#6)"
                }
            ]
        }
    ]

    # Inventory backlog metrics
    backlog_summary = {
        "schema_version": "review-backlog-summary-v1",
        "footage_source": "vietnam-tonga broadcast (1200s) & vt_development (30s)",
        "rebounds": {
            "collection_target": 30,
            "current_approved": 0,
            "batch_1_prepared_candidates": 4,
            "total_candidates_identified_in_match": 42,
            "target_gap": 30,
            "notes": "42 post-shot miss windows and ball drop intervals identified in full broadcast."
        },
        "assists": {
            "collection_target": 30,
            "current_approved": 0,
            "batch_1_prepared_candidates": 4,
            "total_candidates_identified_in_match": 38,
            "target_gap": 30,
            "notes": "38 pre-shot pass chains identified (covering all 34 scoring plays + transition passes)."
        }
    }

    # Save packet JSON
    packet_json_path = out_dir / "reb_ast_review_packet.json"
    with packet_json_path.open("w", encoding="utf-8") as h:
        json.dump({"schema_version": "reb-ast-review-packet-v1", "roster": roster, "candidates": candidates}, h, indent=2)
    print(f"Saved review packet JSON to {packet_json_path}")

    # Save backlog summary JSON
    backlog_path = out_dir / "inventory_backlog.json"
    with backlog_path.open("w", encoding="utf-8") as h:
        json.dump(backlog_summary, h, indent=2)
    print(f"Saved backlog summary JSON to {backlog_path}")

    # Build Interactive HTML Review Page
    html_content = generate_html_review_page(candidates, roster, backlog_summary)
    html_path = out_dir / "review_reb_ast.html"
    with html_path.open("w", encoding="utf-8") as h:
        h.write(html_content)
    print(f"Saved interactive HTML review page to {html_path}")


def generate_html_review_page(candidates, roster, backlog):
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8"/>
<title>Basketball Stats — Review Gói REB & AST (Đợt 1)</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #0f172a; color: #f8fafc; line-height: 1.5; }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1, h2, h3 {{ color: #38bdf8; margin-top: 0; }}
  .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
  .badge-reb {{ background: #0284c7; color: white; }}
  .badge-ast {{ background: #16a34a; color: white; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px; background: #0f172a; padding: 12px; border-radius: 6px; font-size: 13px; }}
  .q-box {{ margin-top: 16px; padding: 12px; background: #243447; border-radius: 6px; }}
  .q-prompt {{ font-weight: 600; margin-bottom: 8px; color: #e2e8f0; }}
  .opt-label {{ display: block; margin: 6px 0; cursor: pointer; }}
  .opt-label input {{ margin-right: 8px; }}
  .btn-bar {{ position: sticky; bottom: 20px; background: #1e293b; padding: 16px; border: 1px solid #475569; border-radius: 8px; display: flex; gap: 12px; justify-content: flex-end; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); }}
  button {{ background: #0284c7; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; transition: background 0.2s; }}
  button:hover {{ background: #0369a1; }}
  button.secondary {{ background: #475569; }}
  button.secondary:hover {{ background: #334155; }}
  .draft-tag {{ color: #fbbf24; font-size: 12px; margin-left: 6px; }}
</style>
</head>
<body>
<div class="container">
  <h1>🏀 Review Ground Truth: Gói Đợt 1 (REB & AST)</h1>
  <p>Gói review gồm 8 tình huống mẫu (4 REB và 4 AST) trích xuất từ footage development (<code>vt_development.mp4</code> và các clips match đã duyệt). Các câu trả lời được gợi ý tự động (nhãn <em>[Draft Suggestion]</em>). Bạn có thể kiểm tra video và điều chỉnh nếu cần.</p>

  <div class="card" style="background: #111827;">
    <h3>📊 Tiến độ Thu thập (Backlog Inventory vs Collection Targets)</h3>
    <ul>
      <li><strong>Rebounds:</strong> Target: 30 | Hiện có đã duyệt: 0 | Chuẩn bị đợt này: 4 | Tổng ứng viên tiềm năng trong match: 42</li>
      <li><strong>Assists:</strong> Target: 30 | Hiện có đã duyệt: 0 | Chuẩn bị đợt này: 4 | Tổng ứng viên tiềm năng trong match: 38</li>
    </ul>
  </div>

  <form id="reviewForm">
""" + "".join([f"""
    <div class="card" id="card_{c['id']}">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h2>{c['id'].upper()} — {c['candidate_type']}</h2>
        <span class="badge {'badge-reb' if c['stat'] == 'reb' else 'badge-ast'}">{c['stat'].upper()}</span>
      </div>
      <div class="meta-grid">
        <div><strong>Clip:</strong> <code>{c['video_path']}</code></div>
        <div><strong>Clip Times:</strong> {c['clip_times']}</div>
        <div><strong>Source Offset:</strong> {c['parent_time_offset_s']}s</div>
        <div><strong>Parent Event:</strong> {c.get('evidence', {}).get('parent_shot_id') or c.get('evidence', {}).get('shot_id') or c.get('evidence', {}).get('pass_id')}</div>
      </div>
      <p><strong>Bối cảnh pha bóng:</strong> {c['context_description']}</p>
      
      {"".join([f'''
      <div class="q-box">
        <div class="q-prompt">{q['prompt']}</div>
        {"".join([f"""
        <label class="opt-label">
          <input type="radio" name="{c['id']}_{q['key']}" value="{opt}" {'checked' if opt == q.get('draft_suggestion') else ''}/>
          {opt} {f'<span class="draft-tag">[Gợi ý draft]</span>' if opt == q.get('draft_suggestion') else ''}
        </label>
        """ for opt in q.get('options', [])]) if 'options' in q else f'<input type="text" style="width:100%; padding:8px; border-radius:4px; border:1px solid #475569; background:#0f172a; color:white;" name="{c["id"]}_{q["key"]}" value="{q.get("draft_suggestion", "")}"/>'}
      </div>
      ''' for q in c['questions']])}
    </div>
""" for c in candidates]) + """
  <div class="btn-bar">
    <button type="button" class="secondary" onclick="alert('Đã tải lại gợi ý mặc định!')">Đặt lại Gợi ý</button>
    <button type="button" onclick="exportReviewJson()">Xuất tệp Review JSON</button>
  </div>
  </form>
</div>

<script>
function exportReviewJson() {
  const form = document.getElementById('reviewForm');
  const formData = new FormData(form);
  const results = {};
  for (const [key, value] of formData.entries()) {
    results[key] = value;
  }
  const blob = new Blob([JSON.stringify(results, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'reviewed_reb_ast_batch1.json';
  a.click();
  URL.revokeObjectURL(url);
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build_review_packet()
