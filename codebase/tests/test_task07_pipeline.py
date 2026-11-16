"""Task07 source binding, lifecycle, export and scoped holdout authorization."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.app import assert_development_video_allowed
from basketball_scoreboard.ball_pipeline import run_ball_pipeline, jsonl
from basketball_scoreboard.spatial_io import file_hash
from basketball_scoreboard.video import VideoWriter


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.video=self.path/'source.mp4'
        with VideoWriter(self.video,400,240,10) as writer:
            for i in range(9):writer.write_frame(np.zeros((240,400,3),dtype=np.uint8),i*.1)
        self.sha=file_hash(self.video)
        self.run=dict(status='completed',is_synthetic=True,run_id='source',video_id='fixture',source_fingerprint_sha256=self.sha,
                      video_metadata=dict(width=400,height=240,fps=10,duration_s=.9),class_mapping={'9':'ball','7':'human'})
        self.frames=[];self.tracks=[]
        for i,x in enumerate((55,55,55,130,180,230,285,285,285)):
            dets=[dict(class_id=9,class_name='ball',xyxy=[x-5,95,x+5,105],confidence=.9)]
            for track,box in [('a',[20,50,90,190]),('b',[250,50,320,190])]:
                dets.append(dict(class_id=7,class_name='human',xyxy=box,confidence=.9))
                self.tracks.append(dict(video_id='fixture',source_run_id='source',source_fingerprint_sha256=self.sha,
                    observation_id=f'{i}:{track}',track_id=track,frame_index=i,source_time_s=i*.1,timestamp_status='valid',
                    camera_id='cam',segment_id='s',bbox=box,sample_type='observed',role='player',team_id='r',player_id=None))
            self.frames.append(dict(video_id='fixture',frame_index=i,source_time_s=i*.1,original_wh=[400,240],timestamp_status='valid',detections=dets))
        self.meta=dict(status='completed',source_run_id='source',source_fingerprint_sha256=self.sha,
                       acceptance_scope='diagnostic',roster_config={'is_synthetic':True})
        self.save()

    def save(self):
        (self.path/'source.json').write_text(json.dumps(self.run),encoding='utf-8')
        (self.path/'detections.jsonl').write_text('\n'.join(json.dumps(x) for x in self.frames)+'\n',encoding='utf-8')
        (self.path/'tracks.jsonl').write_text('\n'.join(json.dumps(x) for x in self.tracks),encoding='utf-8')
        self.meta['input_detections_sha256']=file_hash(self.path/'detections.jsonl')
        (self.path/'tracking.json').write_text(json.dumps(self.meta),encoding='utf-8')

    def execute(self,name='out',**kwargs):
        return run_ball_pipeline(self.path/'detections.jsonl',self.path/'source.json',self.path/'tracks.jsonl',
                                 self.path/'tracking.json',self.path/name,**{'diagnostic':True,**kwargs})

    def test_end_to_end_export_and_replay(self):
        summary=self.execute(video=self.video)
        self.assertTrue(summary['replay_verified'])
        self.assertEqual(summary['frames'],9)
        self.assertEqual(summary['video_export']['frames'],9)
        self.assertLessEqual(summary['video_export']['max_pts_error_s'],2e-6)
        self.assertTrue((self.path/'out/timeline.png').is_file())
        self.assertIsNone(summary['metrics']['control_accuracy'])
        second=self.execute('second',video=self.video)
        self.assertEqual(summary['namespace'],second['namespace'])
        for file in ('ball_tracks.jsonl','ball_control.jsonl','passes.jsonl','possessions.jsonl','transitions.jsonl'):
            self.assertEqual((self.path/'out'/file).read_bytes(),(self.path/'second'/file).read_bytes())

    def test_output_not_overwritten(self):
        (self.path/'out').mkdir();(self.path/'out/sentinel').write_text('keep')
        with self.assertRaises(FileExistsError):self.execute()
        self.assertEqual((self.path/'out/sentinel').read_text(),'keep')

    def test_diagnostic_upstream_cannot_be_promoted(self):
        with self.assertRaises(ValueError):self.execute(diagnostic=False)

    def test_source_and_clock_mismatch_rejected(self):
        self.tracks[0]['source_time_s']=.001;self.save()
        with self.assertRaises(ValueError):self.execute()

    def test_observation_requires_detection(self):
        self.tracks[0]['bbox']=[100,50,150,190];self.save()
        with self.assertRaises(ValueError):self.execute()

    def test_future_or_missing_identity_mapping_rejected(self):
        self.tracks[0]['player_id']='p';self.save()
        with self.assertRaises(ValueError):self.execute()
        mapping=[dict(track_id='a',start_time_s=.1,end_time_s=.8,revision_id=1,team_id='r',player_id='p')]
        (self.path/'identity.json').write_text(json.dumps(mapping))
        with self.assertRaises(ValueError):self.execute(identity_mappings=self.path/'identity.json')

    def test_cut_prevents_flight_confirmation(self):
        exclusion=dict(source_video_sha256=self.sha,intervals=[dict(start_time_s=.35,end_time_s=.35,reason='cut')])
        (self.path/'exclusions.json').write_text(json.dumps(exclusion))
        self.execute(exclusions=self.path/'exclusions.json')
        self.assertFalse(any(p['outcome']=='completed' for p in jsonl(self.path/'out/passes.jsonl')))

    def test_estimated_clock_cannot_confirm(self):
        self.frames[4]['timestamp_status']='estimated'
        for row in self.tracks:
            if row['frame_index']==4:row['timestamp_status']='estimated'
        self.save();self.execute()
        self.assertEqual(jsonl(self.path/'out/ball_tracks.jsonl')[4]['sample_type'],'missing')
        self.assertIsNone(jsonl(self.path/'out/ball_control.jsonl')[4]['controller'])

    def test_no_people_still_produces_ball_timeline(self):
        self.tracks=[];self.save()
        summary=self.execute()
        self.assertEqual(summary['possession_count'],0)
        self.assertEqual(summary['frames'],9)

    def test_predicted_box_outside_image_is_not_observed_evidence(self):
        self.tracks[0].update(sample_type='predicted',bbox=[-10,50,60,190])
        self.save();self.execute()
        self.assertIsNone(jsonl(self.path/'out/ball_control.jsonl')[0]['controller'])

    def test_writer_failure_has_failed_metadata(self):
        with patch('basketball_scoreboard.ball_pipeline.export_debug_video',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.execute(video=self.video)
        meta=json.loads((self.path/'out/run.json').read_text())
        self.assertEqual(meta,{'status':'failed','error_class':'OSError'})


class ExposureTests(unittest.TestCase):
    def test_default_remains_protected_and_explicit_clip04_is_allowed(self):
        authorization=ROOT/'configs/development_authorizations/task07-clip04.json'
        decision=json.loads(authorization.read_text())
        sha=decision['allowed_video_sha256']
        with self.assertRaises(ValueError):assert_development_video_allowed(sha)
        assert_development_video_allowed(sha,authorization_path=authorization)
        for other in decision['exposed_group_sha256']:
            if other != sha:
                with self.assertRaises(ValueError):assert_development_video_allowed(other,authorization_path=authorization)

    def test_incomplete_group_exposure_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            decision=json.loads((ROOT/'configs/development_authorizations/task07-clip04.json').read_text())
            decision['exposed_group_sha256']=[decision['allowed_video_sha256']]
            path=Path(directory)/'bad.json';path.write_text(json.dumps(decision))
            with self.assertRaises(ValueError):assert_development_video_allowed(decision['allowed_video_sha256'],authorization_path=path)


if __name__=='__main__':unittest.main()
