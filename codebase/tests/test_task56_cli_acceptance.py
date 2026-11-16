"""Real CLI adapters with tiny local media; no API keys, OCR weights or GT leakage."""
from contextlib import redirect_stdout,redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.video import VideoWriter
from basketball_scoreboard.spatial_io import file_hash
from track_players import track_players_pipeline
from generate_heatmap import generate_heatmap_pipeline


class SpatialCLIAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.video=self.path/'source.mp4'
        with VideoWriter(self.video,64,64,10) as writer:
            for t in (0,.1,.2):
                image=np.zeros((64,64,3),dtype=np.uint8)
                image[:]=(30,30,220)
                writer.write_frame(image,t)
        self.sha=file_hash(self.video)
        self.run={'status':'completed','is_synthetic':True,'run_id':'fixture-run','video_id':'synthetic',
                  'source_fingerprint_sha256':self.sha,'video_metadata':{'width':64,'height':64,'duration_s':.3},
                  'class_mapping':{'0':'ball','1':'human','2':'rim'}}
        self.frames=[dict(video_id='synthetic',frame_index=i,source_time_s=t,original_wh=[64,64],timestamp_status='valid',
                          detections=[dict(class_name='human',class_id=1,confidence=.9,xyxy=[10,8,50,56])])
                     for i,t in enumerate((0,.1,.2))]
        self.meta=self.path/'source-run.json'
        self.input=self.path/'detections.jsonl'
        self.court=self.path/'court.json'
        config={'schema_version':'2.0.1','camera_id':'fixture','segment_id':'fixture-segment','status':'draft','is_synthetic':True,
                'original_image_wh':[64,64],'source_video_hash':self.sha,
                'court_coordinate_system':{'origin':'corner','axes':{},'units':'normalized',
                                           'court_bounds':{'x_min':0,'x_max':10,'y_min':0,'y_max':10}},
                'court_roi_image':[[0,0],[64,0],[64,64],[0,64]],
                'point_correspondences':[dict(point_id=str(i),image_xy=image,court_xy=court)
                    for i,(image,court) in enumerate(zip([[0,0],[64,0],[64,64],[0,64]],[[0,0],[10,0],[10,10],[0,10]]))]}
        self.court.write_text(json.dumps(config))
        self.roster=self.path/'roster.json'
        self.roster.write_text(json.dumps(dict(team_a_id='red',team_b_id='blue',is_synthetic=True,provenance_status='draft',
                  team_a_color_rgb=[220,30,30],team_b_color_rgb=[30,60,220],players=[])))
        self.save()

    def save(self):
        self.meta.write_text(json.dumps(self.run))
        self.input.write_text('\n'.join(json.dumps(row) for row in self.frames)+'\n')

    def track(self,output,**kwargs):
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            return track_players_pipeline(str(self.input),str(output),run_json_path=str(self.meta),**kwargs)

    def heat(self,input_path,output,**kwargs):
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            return generate_heatmap_pipeline(str(self.court),str(input_path),str(output),run_json_path=str(self.meta),**kwargs)

    def test_real_video_color_reaches_resolver_without_ocr(self):
        out=self.path/'track'
        self.assertEqual(self.track(out,roster_config_path=str(self.roster),video_path=str(self.video),allow_uncalibrated=True),0)
        records=[json.loads(line) for line in (out/'tracked_observations.jsonl').read_text().splitlines()]
        self.assertTrue(any(row['team_id']=='red' for row in records))
        self.assertTrue(all(row['player_id'] is None for row in records))
        summary=json.loads((out/'tracking_summary.json').read_text())
        self.assertEqual(summary['team_color_evidence_count'],3)
        self.assertEqual(summary['acceptance_scope'],'diagnostic')

    def test_existing_output_is_never_overwritten(self):
        out=self.path/'existing';out.mkdir()
        sentinel=out/'tracked_observations.jsonl';sentinel.write_text('preserve')
        self.assertNotEqual(self.track(out,allow_uncalibrated=True),0)
        self.assertEqual(sentinel.read_text(),'preserve')

    def test_declared_missing_court_is_not_silently_ignored(self):
        self.assertNotEqual(self.track(self.path/'bad',court_config_path=str(self.path/'absent.json')),0)

    def test_frame_identity_and_dimensions_are_checked(self):
        for mutate in ('video','dimensions','clock'):
            with self.subTest(mutate=mutate):
                original=json.loads(json.dumps(self.frames))
                if mutate=='video':self.frames[0]['video_id']='other'
                if mutate=='dimensions':self.frames[0]['original_wh']=[128,64]
                if mutate=='clock':self.frames[1]['source_time_s']=0
                self.save()
                self.assertNotEqual(self.track(self.path/mutate,allow_uncalibrated=True),0)
                self.frames=original

    def test_renamed_holdout_is_rejected_by_fingerprint(self):
        v1=json.loads((ROOT/'data/splits.json').read_text())
        import csv
        reserved=set(v1['proposed_split']['test']['video_ids'])
        with (ROOT/'data/manifest.csv').open(encoding='utf-8') as handle:
            sha=next(row['sha256'] for row in csv.DictReader(handle) if row['video_id'] in reserved)
        self.run['source_fingerprint_sha256']=sha;self.save()
        self.assertNotEqual(self.track(self.path/'holdout-renamed',allow_uncalibrated=True),0)

    def test_synthetic_calibration_requires_diagnostic_opt_in(self):
        self.run['is_synthetic']=False
        self.run['runtime']={'model_id':'phung-van-tri/basketball-xil7x-y8g6u-1-yolo26s-t1'}
        self.save()
        self.assertNotEqual(self.heat(self.input,self.path/'production'),0)

    def test_calibration_source_binding_rejects_mismatch(self):
        config=json.loads(self.court.read_text());config['source_video_hash']='b'*64
        self.court.write_text(json.dumps(config))
        self.assertNotEqual(self.heat(self.input,self.path/'mismatch',allow_uncalibrated=True),0)

    def test_trackless_input_has_no_invented_trajectory_mass(self):
        out=self.path/'raw-heat'
        self.assertEqual(self.heat(self.input,out,allow_uncalibrated=True),0)
        summary=json.loads((out/'heatmap_summary.json').read_text())
        self.assertEqual(summary['heatmap_metadata']['total_player_seconds'],0)
        self.assertEqual(summary['input_kind'],'trackless_detections')

    def test_projection_does_not_promote_predicted_samples(self):
        out=self.path/'track'
        self.frames[1]['detections']=[];self.save()
        self.assertEqual(self.track(out,court_config_path=str(self.court),allow_uncalibrated=True,min_hits=1),0)
        projected=self.path/'heat'
        self.assertEqual(self.heat(out/'tracked_observations.jsonl',projected,allow_uncalibrated=True,verify_replay=True),0)
        records=[json.loads(line) for line in (projected/'trajectories.jsonl').read_text().splitlines()]
        predictions=[row for row in records if row['sample_type']=='predicted']
        self.assertEqual(len(predictions),1)
        self.assertEqual(predictions[0]['validity_status'],'predicted_occluded')
        summary=json.loads((projected/'heatmap_summary.json').read_text())
        self.assertEqual(summary['heatmap_metadata']['total_player_seconds'],0)

    def test_track_players_cli_with_mock_ocr_in_diagnostic_mode(self):
        out = self.path / 'track_mock_ocr'
        res = self.track(out, roster_config_path=str(self.roster), video_path=str(self.video),
                         allow_uncalibrated=True, enable_ocr=True, ocr_provider='mock')
        self.assertEqual(res, 0)
        self.assertTrue((out / 'jersey_evidence.json').is_file())
        summary = json.loads((out / 'tracking_summary.json').read_text())
        self.assertEqual(summary['ocr_status'], 'enabled_mock')
        self.assertEqual(summary['ocr_provider'], 'mock')

    def test_track_players_cli_mock_ocr_forbidden_in_production(self):
        out = self.path / 'track_mock_prod'
        res = self.track(out, roster_config_path=str(self.roster), video_path=str(self.video),
                         allow_uncalibrated=False, enable_ocr=True, ocr_provider='mock')
        self.assertNotEqual(res, 0)

    def test_track_players_cli_easyocr_production_fails_when_weights_missing(self):
        out = self.path / 'track_easyocr_missing'
        res = self.track(out, roster_config_path=str(self.roster), video_path=str(self.video),
                         allow_uncalibrated=False, enable_ocr=True, ocr_provider='easyocr')
        self.assertNotEqual(res, 0)

if __name__=='__main__':
    unittest.main()
