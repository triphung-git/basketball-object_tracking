#!/usr/bin/env python3
"""Project local observations and export auditable time-weighted occupancy."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.court import CourtConfig,CourtModel,TrajectoryObservation
from basketball_scoreboard.heatmap import HeatmapAccumulator,ExclusionInterval
from basketball_scoreboard.spatial_io import load_spatial_input,new_output,file_hash,write_json,emit_observations,runtime_snapshot


def generate_heatmap_pipeline(court_config_path,detections_jsonl_path,output_dir,run_json_path=None,
                              allow_uncalibrated=False,max_gap_s=1.,timestamp_policy='allow_repaired_with_warning',
                              grid_shape=(50,50),verify_replay=False,exclusions_path=None,team_a_id=None,team_b_id=None):
    output=None
    try:
        runtime=runtime_snapshot(__file__)
        config=CourtConfig.from_json_file(court_config_path)
        first=next(line for line in Path(detections_jsonl_path).read_text(encoding='utf-8').splitlines() if line.strip())
        tracked='observation_id' in json.loads(first)
        run,records=load_spatial_input(detections_jsonl_path,run_json_path,config,tracked,allow_uncalibrated)
        model=CourtModel(config)
        model.calibrate(allow_uncalibrated=allow_uncalibrated)
        observations=[]
        for item in records:
            if tracked:
                obs=TrajectoryObservation(**item)
                # Reproject from raw image point; never promote visibility/sample validity.
                obs.projected_court_xy=None
                obs.calibration_version=model.calibration_version
                obs.court_units=config.court_coordinate_system.units
                geometry_status=obs.validity_status in {'valid','outside_roi','outside_court_bounds','degenerate_projection'}
                if model.is_in_court_roi(obs.footpoint_image):
                    point=model.project_image_to_court(obs.footpoint_image)
                    if point is not None and model.is_in_court_bounds(point):
                        obs.projected_court_xy=point
                        if geometry_status:
                            obs.validity_status='valid'
                            obs.validity_reason=None
                    elif geometry_status:
                        obs.validity_status='outside_court_bounds'
                elif geometry_status:
                    obs.validity_status='outside_roi'
                observations.append(obs)
            else:
                for offset,det in enumerate(item.get('detections',[])):
                    if det.get('class_name')!='human':
                        continue
                    observations.append(model.process_detection(
                        det['xyxy'],item['frame_index'],item['source_time_s'],item['timestamp_status'],
                        item['video_id'],run['source_fingerprint_sha256'],run['run_id'],
                        f"obs_{item['frame_index']}_{offset}",confidence=det['confidence']))
        exclusions=[ExclusionInterval(**row) for row in json.loads(Path(exclusions_path).read_text(encoding='utf-8'))] if exclusions_path else []
        tracking_summary=Path(detections_jsonl_path).parent/'tracking_summary.json'
        sidecar=json.loads(tracking_summary.read_text(encoding='utf-8')) if tracked and tracking_summary.is_file() else {}
        teams=sidecar.get('team_ids',['team_a','team_b'])
        accumulator=HeatmapAccumulator(config.court_coordinate_system.court_bounds,grid_shape,config.court_coordinate_system.units,
                                       team_a_id or teams[0],team_b_id or teams[1],max_gap_s,timestamp_policy,exclusions,
                                       allow_unknown_role=allow_uncalibrated)
        accumulator.process_observations_batch(observations)
        conserved,total,components=accumulator.verify_mass_conservation()
        if not conserved:
            raise ValueError('Grid mass mismatch')
        replay_verified=False
        if verify_replay:
            before=accumulator.total_grid.copy()
            accumulator.recompute(observations)
            import numpy as np
            if not np.allclose(before,accumulator.total_grid,rtol=0,atol=1e-12):
                raise ValueError('Replay changed the grid')
            replay_verified=True
        output=new_output(output_dir,[detections_jsonl_path,run_json_path,court_config_path,exclusions_path])
        emit_observations(output/'trajectories.jsonl',observations)
        accumulator.export_raw_grid(str(output/'heatmap_raw_grid.json'))
        title='DIAGNOSTIC synthetic/uncalibrated human occupancy' if allow_uncalibrated else 'Observed player occupancy'
        accumulator.render_png(str(output/'heatmap_total.png'),title=title)
        summary=dict(status='completed',runtime=runtime,acceptance_scope='diagnostic' if allow_uncalibrated else 'technical',
                     geometry_data_acceptance='pending' if allow_uncalibrated else 'requires_independent_GT_evaluation',
                     court_config=config.to_dict(),calibration_version=model.calibration_version,
                     source_run_id=run['run_id'],source_video_hash=run['source_fingerprint_sha256'],
                     input_sha256=file_hash(detections_jsonl_path),input_kind='tracked_observations' if tracked else 'trackless_detections',
                     observations_count=len(observations),valid_court_observations=sum(o.validity_status=='valid' for o in observations),
                     team_ids=[accumulator.team_a_id,accumulator.team_b_id],trackless_policy='not_integrated',
                     temporal_policy='adjacent_observed_valid_endpoints; invalid/predicted are barriers; no final extrapolation',
                     role_policy='unknown_human_allowed_in_diagnostic_only' if allow_uncalibrated else 'player_evidence_required',
                     exclusions=[vars(e) for e in exclusions],replay_verified=replay_verified,
                     heatmap_metadata=accumulator.metadata.to_dict(),
                     mass_conservation=dict(is_conserved=conserved,total_mass_player_seconds=total,components_sum_player_seconds=components),
                     geometry_metrics=dict(median_error=None,reason='No independently reviewed visible-foot GT'))
        write_json(output/'heatmap_summary.json',summary)
        write_json(output/'run.json',summary)
        print(f"Completed: {len(observations)} observations, {total:.6f} occupancy seconds ({summary['acceptance_scope']})")
        return 0
    except Exception as error:
        if output:
            write_json(output/'run.json',dict(status='failed',error_class=type(error).__name__))
        print(f"Heatmap failed ({type(error).__name__}); input/config validation or processing failed",file=sys.stderr)
        return 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--court-config',required=True)
    parser.add_argument('--detections',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--run-json',required=True)
    parser.add_argument('--allow-uncalibrated',action='store_true')
    parser.add_argument('--max-gap-s',type=float,default=1.)
    parser.add_argument('--policy',default='allow_repaired_with_warning',choices=['strict_valid','allow_repaired_with_warning','allow_irregular'])
    parser.add_argument('--verify-replay',action='store_true')
    parser.add_argument('--exclusions',help='Operational exclusion JSON list (start_s,end_s,reason); no GT lookup')
    parser.add_argument('--team-a-id')
    parser.add_argument('--team-b-id')
    args=parser.parse_args()
    return generate_heatmap_pipeline(args.court_config,args.detections,args.output_dir,args.run_json,
                                     args.allow_uncalibrated,args.max_gap_s,args.policy,verify_replay=args.verify_replay,
                                     exclusions_path=args.exclusions,team_a_id=args.team_a_id,team_b_id=args.team_b_id)


if __name__=='__main__':
    sys.exit(main())
