import json

import numpy as np

from basketball_scoreboard.spatial_analysis import (
    SpatialProjector,
    build_spatial_analysis,
    default_config,
    validate_config,
)


def _job():
    return {
        "width": 200,
        "height": 240,
        "duration_s": 1.0,
        "source_sha256": "source-hash",
    }


def _roster():
    return {
        "team_a_id": "a",
        "team_b_id": "b",
        "team_a_name": "A",
        "team_b_name": "B",
        "team_a_color_rgb": [220, 30, 30],
        "team_b_color_rgb": [30, 30, 220],
        "players": [
            {"player_id": "a7", "team_id": "a", "jersey_number": "7", "name": "Player 7"}
        ],
    }


def _points():
    court_points = [(-2, 1), (2, 1), (-2, 8), (2, 8), (0, 5)]
    return [
        {"court": list(court), "image": [100 + court[0] * 10, 200 - court[1] * 10]}
        for court in court_points
    ]


def _observation(time_s, **updates):
    observation = {
        "source_time_s": time_s,
        "timestamp_status": "valid",
        "sample_type": "observed",
        "track_id": "track-1",
        "role": "player",
        "bbox": [90, 110, 110, 160],
        "footpoint_image": [100, 150],
        "validity_status": "valid",
    }
    observation.update(updates)
    return observation


def test_spatial_analysis_projects_observed_tracks_and_weights_heatmap(tmp_path):
    tracking = tmp_path / "analysis" / "tracking"
    tracking.mkdir(parents=True)
    config = default_config(_job(), _roster())
    config["segments"] = [
        {"start_s": 0, "end_s": 1, "anchor_s": 0, "points": _points()}
    ]
    config["assignments"] = [
        {
            "track_id": "track-1",
            "role": "player",
            "player_id": "a7",
            "team_id": "a",
            "start_s": 0,
            "end_s": 1,
        }
    ]
    rows = [
        _observation(0),
        _observation(0.2),
        _observation(0.4, validity_status="invalid"),
        _observation(0.6, sample_type="predicted"),
    ]
    (tracking / "tracked_observations.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows), encoding="utf-8"
    )

    result = build_spatial_analysis(tmp_path, config)

    assert result["status"] == "completed"
    assert result["tracks"][0]["player_id"] == "a7"
    assert [frame["time"] for frame in result["frames"]] == [0, 0.2, 0.4]
    assert result["frames"][0]["players"][0]["xy"] == [0.0, 5.0]
    assert np.isclose(np.asarray(result["heatmaps"]["all"]).sum(), 0.2)
    assert not {"points", "assists", "rebounds", "shots", "events", "boxscore"} & result.keys()


def test_spatial_config_strips_legacy_statistics_fields():
    job = _job()
    config = default_config(job, _roster())
    config["points"] = [{"source_time_s": 0.5, "value": 2}]
    config["shot_summary"] = {"made": 1}
    config["events"] = [{"type": "made_shot"}]

    normalized = validate_config(config, job)

    assert not {"points", "shot_summary", "events", "boxscore"} & normalized.keys()


def test_spatial_projector_rejects_points_outside_court():
    config = default_config(_job(), _roster())
    config["segments"] = [
        {"start_s": 0, "end_s": 1, "anchor_s": 0, "points": _points()}
    ]

    projector = SpatialProjector(config)

    assert projector.project([100, 150], 0.5)[0] == [0.0, 5.0]
    assert projector.project([0, 0], 0.5)[0] is None
