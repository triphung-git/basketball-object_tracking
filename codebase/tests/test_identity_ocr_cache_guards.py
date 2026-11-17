"""Reject cross-source or mock OCR caches before any OCR model is initialized."""
import json
from unittest import TestCase
from unittest.mock import patch

import test_task56_cli_acceptance as fixtures
from basketball_scoreboard.spatial_io import file_hash


class OCRCacheGuards(TestCase):
    setUp=fixtures.SpatialCLIAcceptanceTests.setUp
    save=fixtures.SpatialCLIAcceptanceTests.save
    track=fixtures.SpatialCLIAcceptanceTests.track

    def cache(self,**changes):
        cache=self.path/'cache';cache.mkdir()
        metadata=dict(status='completed',ocr_status='enabled_easyocr_local',
                      source_fingerprint_sha256=self.sha,input_detections_sha256=file_hash(self.input),
                      runtime_config=dict(max_age_s=1.,min_hits=3))
        metadata.update(changes)
        (cache/'run.json').write_text(json.dumps(metadata),encoding='utf-8')
        return cache

    def test_cross_video_cache_is_rejected_without_ocr_initialization(self):
        cache=self.cache(source_fingerprint_sha256='b'*64)
        with patch('track_players.LocalEasyOCRProvider') as provider:
            self.assertEqual(self.track(self.path/'out',allow_uncalibrated=True,enable_ocr=True,
                                       jersey_evidence_cache=cache),1)
            provider.assert_not_called()

    def test_mock_cache_cannot_be_promoted_to_real_ocr(self):
        cache=self.cache(ocr_status='enabled_mock')
        with patch('track_players.LocalEasyOCRProvider') as provider:
            self.assertEqual(self.track(self.path/'out',allow_uncalibrated=True,enable_ocr=True,
                                       jersey_evidence_cache=cache),1)
            provider.assert_not_called()
