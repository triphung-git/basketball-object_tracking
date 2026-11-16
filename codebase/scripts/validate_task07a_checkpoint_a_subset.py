#!/usr/bin/env python3
"""Fail-closed structural validation for a returned Task07 checkpoint-A subset."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from basketball_scoreboard.dataset_review_validation import validate_task07a_checkpoint_subset
from basketball_scoreboard.spatial_io import file_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed', required=True, help='JSON exported by review.html')
    parser.add_argument('--manifest', required=True, help='Unmodified review-manifest.json')
    parser.add_argument('--codebase', default=str(ROOT), help='Codebase containing the bound source artifacts')
    args = parser.parse_args()
    try:
        codebase = Path(args.codebase).resolve()
        manifest_path = Path(args.manifest).resolve()
        reviewed_path = Path(args.reviewed).resolve()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        reviewed = json.loads(reviewed_path.read_text(encoding='utf-8-sig'))
        inputs = {}
        for key, relative in manifest['input_paths'].items():
            path = (codebase / relative).resolve()
            if not path.is_relative_to(codebase) or not path.is_file():
                raise ValueError(f'Bound source input is missing or outside codebase: {relative}')
            actual_hash = file_hash(path)
            if actual_hash != manifest['input_sha256'].get(key):
                raise ValueError(f'Bound source input changed: {relative}')
            inputs[key] = path
        manifest_sha256 = file_hash(manifest_path)
        result = validate_task07a_checkpoint_subset(
            reviewed,
            manifest,
            json.loads(inputs['pilot'].read_text(encoding='utf-8-sig')),
            json.loads(inputs['progress'].read_text(encoding='utf-8-sig')),
            json.loads(inputs['identity_packet'].read_text(encoding='utf-8-sig')),
            manifest_sha256,
        )
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        print(f'Checkpoint-A subset validation failed ({type(error).__name__}): {error}',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
