"""SDK receives WH overrides; network diagnostics preserve coordinates and session."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from basketball_scoreboard.detector import ObjectDetector
from basketball_scoreboard.config import ModelConfig
from basketball_scoreboard.preprocessing_diagnostics import observe_cpu_session,serializable_metadata,letterbox_image,unletterbox_xyxy


class PreprocessingContractTests(unittest.TestCase):
    def test_letterbox_round_trip_non_square_source(self):
        image=np.zeros((1080,1920,3),dtype=np.uint8)
        boxed,transform=letterbox_image(image)
        self.assertEqual(boxed.shape,(640,640,3))
        original=[300.,200.,600.,400.]
        mapped=[original[0]*transform['scale_x']+transform['pad_left'],original[1]*transform['scale_y']+transform['pad_top'],
                original[2]*transform['scale_x']+transform['pad_left'],original[3]*transform['scale_y']+transform['pad_top']]
        self.assertTrue(np.allclose(unletterbox_xyxy(mapped,transform),original))

    def test_letterbox_rounding_uses_actual_axis_scales(self):
        _,transform=letterbox_image(np.zeros((333,1001,3),dtype=np.uint8))
        nw,nh=transform['resized_wh']
        full=[transform['pad_left'],transform['pad_top'],transform['pad_left']+nw,transform['pad_top']+nh]
        self.assertTrue(np.allclose(unletterbox_xyxy(full,transform),[0,0,1001,333]))

    def test_padding_only_detection_does_not_become_source_detection(self):
        _,transform=letterbox_image(np.zeros((1080,1920,3),dtype=np.uint8))
        self.assertIsNone(unletterbox_xyxy([10,10,20,20],transform))

    def detector(self):
        detector=ObjectDetector.__new__(ObjectDetector)
        detector.config=ModelConfig(max_edge=1280,confidence_threshold=.15)
        detector.class_mapping={0:'ball',1:'human',2:'rim'}
        prediction=SimpleNamespace(to_supervision=lambda:SimpleNamespace(
            xyxy=np.array([[64.,32.,128.,96.]]),class_id=np.array([0]),confidence=np.array([.8])))
        detector.model=Mock(return_value=[prediction])
        return detector

    def test_size_is_forwarded_but_sdk_source_coordinate_mapping_is_not_applied_twice(self):
        detector=self.detector()
        rows,_=detector.detect(np.zeros((1080,1920,3),dtype=np.uint8),image_size=(960,960))
        self.assertEqual(detector.model.call_args.kwargs,dict(confidence=.15,image_size=(960,960)))
        self.assertEqual(detector.model.call_args.args[0].shape[:2],(720,1280))
        self.assertEqual(rows[0].xyxy,[96.,48.,192.,144.])

    def test_default_sdk_options_remain_unchanged(self):
        detector=self.detector();detector.detect(np.zeros((100,200,3),dtype=np.uint8))
        self.assertEqual(detector.model.call_args.kwargs,dict(confidence=.15))

    def test_bad_sizes_rejected_before_inference(self):
        for size in ((True,640),(641,640),(0,640),(4096,640),(640,),640):
            detector=self.detector()
            with self.subTest(size=size):
                with self.assertRaises(ValueError):detector.detect(np.zeros((10,10,3),dtype=np.uint8),image_size=size)
                detector.model.assert_not_called()

    def test_actual_feed_shape_is_recorded_and_original_session_restored(self):
        original=SimpleNamespace(get_providers=lambda:['CPUExecutionProvider'],run=Mock(return_value=['ok']))
        model=SimpleNamespace(_session=original)
        with observe_cpu_session(model) as recorded:
            self.assertEqual(model._session.run(None,{'images':np.zeros((1,3,960,960))}),['ok'])
        self.assertEqual(recorded,[{'images':[1,3,960,960]}])
        self.assertIs(model._session,original)

    def test_original_session_restored_after_error(self):
        original=SimpleNamespace(get_providers=lambda:['CPUExecutionProvider'])
        model=SimpleNamespace(_session=original)
        with self.assertRaises(RuntimeError):
            with observe_cpu_session(model):raise RuntimeError('fixture')
        self.assertIs(model._session,original)

    def test_gpu_is_not_silently_observed(self):
        model=SimpleNamespace(_session=SimpleNamespace(get_providers=lambda:['CUDAExecutionProvider']))
        with self.assertRaises(ValueError):
            with observe_cpu_session(model):pass


if __name__=='__main__':unittest.main()
