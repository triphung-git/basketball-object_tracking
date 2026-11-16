#!/usr/bin/env python3
"""Create short local videos with parent provenance and a confirmed-roster config."""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from basketball_scoreboard.app import assert_development_video_allowed
from basketball_scoreboard.identity import RosterConfig
from basketball_scoreboard.spatial_io import file_hash, new_output, write_json
from basketball_scoreboard.video import probe_video


def prepare(source, roster_csv, segment_config, output_dir):
    source, roster_csv = Path(source).resolve(), Path(roster_csv).resolve()
    declaration = json.loads(Path(segment_config).read_text(encoding="utf-8"))
    parent = probe_video(source)
    assert_development_video_allowed(parent.sha256)
    if declaration["parent_sha256"] != parent.sha256:
        raise ValueError("Segment declaration source hash mismatch")
    if declaration.get("roster_review_status") != "approved_by_user_20261104":
        raise ValueError("Explicit confirmed-roster record required")
    with roster_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    teams = list(dict.fromkeys(r["team_id"] for r in rows))
    if len(teams) != 2:
        raise ValueError("Two teams required")
    config = dict(is_synthetic=False, provenance_status="approved", session_id=declaration["source_group"],
                  approval_record="User confirmed proposed roster in conversation 2026-11-04",
                  team_a_id=teams[0], team_b_id=teams[1],
                  team_a_name=next(r["team_name"] for r in rows if r["team_id"]==teams[0]),
                  team_b_name=next(r["team_name"] for r in rows if r["team_id"]==teams[1]),
                  team_a_color_rgb=[180,35,45], team_b_color_rgb=[220,220,225], players=[],
                  color_provenance="Initial red/white prototypes; verify from actual torso crops",
                  roster_csv_sha256=file_hash(roster_csv))
    for row in rows:
        if not row["jersey_number"].strip() or row["is_active"].lower() not in {"true","false"}:
            raise ValueError("Jersey and boolean roster eligibility required")
        config["players"].append(dict(player_id=row["player_id"], team_id=row["team_id"],
            jersey_number=row["jersey_number"].strip(), name=row["name"], is_active=row["is_active"].lower()=="true"))
    RosterConfig.from_dict(config)
    segments = declaration["segments"]
    ids=set()
    for seg in segments:
        name, start, duration = seg["segment_id"], seg["start_s"], seg["duration_s"]
        if Path(name).name != name or name in {".",".."} or name in ids:
            raise ValueError("Unsafe or duplicate segment name")
        if not all(math.isfinite(x) for x in (start,duration)) or not 0 <= start < parent.duration_s or not 30 <= duration <= 60 or start+duration > parent.duration_s:
            raise ValueError("Segments must be 30-60 seconds within the source")
        ids.add(name)
    out = new_output(output_dir,[source,roster_csv,segment_config])
    write_json(out/"run.json",dict(status="running"))
    try:
        write_json(out/"roster.json",config)
        records=[]
        for seg in segments:
            path=out/(seg["segment_id"]+".mp4")
            command=["ffmpeg","-nostdin","-v","error","-n","-ss",str(seg["start_s"]),"-i",str(source),
                     "-t",str(seg["duration_s"]),"-map","0:v:0","-an","-c:v","libx264","-preset","fast","-crf","18","-fps_mode","passthrough",str(path)]
            result=subprocess.run(command,capture_output=True,timeout=300)
            if result.returncode:
                raise RuntimeError("Segment transcoding failed")
            child=probe_video(path)
            import av
            with av.open(str(path)) as handle:
                pts=[float(f.pts*f.time_base) for f in handle.decode(video=0)]
            if not pts or any(b<=a for a,b in zip(pts,pts[1:])) or abs(pts[0])>1e-6 or abs(child.duration_s-seg["duration_s"])>1/parent.fps:
                raise ValueError("Segment timeline validation failed")
            records.append(dict(**seg,media=path.name,child=child.to_dict(),decoded_frames=len(pts),
                parent_sha256=parent.sha256,parent_time_offset_s=seg["start_s"],
                time_mapping="parent_time_s = segment_source_time_s + parent_time_offset_s",
                full_segment_decode=True,transcoded=True,pixel_identical=False))
        summary=dict(status="completed",parent=parent.to_dict(),source_group=declaration["source_group"],
                     declaration_sha256=file_hash(segment_config),segments=records,roster_sha256=file_hash(out/"roster.json"),
                     note="Same match development/validation; no independent match-level generalization claim")
        write_json(out/"segments.json",summary);write_json(out/"run.json",summary)
        return summary
    except Exception as error:
        write_json(out/"run.json",dict(status="failed",error_class=type(error).__name__))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("source","roster-csv","segment-config","output-dir"):parser.add_argument("--"+name,required=True)
    args=parser.parse_args()
    try:
        result=prepare(**vars(args));print(f"Prepared {len(result['segments'])} verified segments and confirmed roster")
        return 0
    except Exception as error:
        print(f"Preparation failed ({type(error).__name__})",file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
