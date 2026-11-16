#!/usr/bin/env python3
"""Refresh the offline review UI while preserving its packet and manifest."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from basketball_scoreboard.spatial_io import file_hash, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir', required=True)
    parser.add_argument('--roster-config')
    args = parser.parse_args()
    folder = Path(args.review_dir).resolve()
    packet_path, manifest_path = folder/'review-packet.json', folder/'review-manifest.json'
    packet = json.loads(packet_path.read_text(encoding='utf-8-sig'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if packet['schema_version'] != 'task07a-checkpoint-a-review-1' or packet['manifest_sha256'] != file_hash(manifest_path):
        raise ValueError('Review schema or manifest binding differs')
    labels = {}
    if args.roster_config:
        roster = json.loads(Path(args.roster_config).read_text(encoding='utf-8-sig'))
        labels = {roster['team_a_id']: roster['team_a_name'], roster['team_b_id']: roster['team_b_name']}
    template_path = ROOT/'scripts/task07a_checkpoint_a_review_simple.html'
    template = template_path.read_text(encoding='utf-8')
    if template.count('__REVIEW_DATA__') != 1:
        raise ValueError('Expected one review data placeholder')
    data = dict(packet=packet, clips=manifest['context_clips'], team_labels=labels)
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    page, backup = folder/'review.html', folder/'review-before-simplify.html'
    if page.exists() and not backup.exists():
        shutil.copyfile(page, backup)
    source_hashes = dict(packet=file_hash(packet_path), manifest=file_hash(manifest_path))
    page.write_text(template.replace('__REVIEW_DATA__', encoded), encoding='utf-8')
    if source_hashes != dict(packet=file_hash(packet_path), manifest=file_hash(manifest_path)):
        raise ValueError('Source packet or manifest changed while rendering')
    write_json(folder/'review-ui-update.json', dict(
        status='rendered_pending_browser_QA', template_sha256=file_hash(template_path),
        renderer_sha256=file_hash(__file__), html_sha256=file_hash(page),
        source_hashes=source_hashes, backup_file=backup.name,
        annotations_modified=False, inference_performed=False,
    ))
    print('Updated review UI; source packet and manifest preserved.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
