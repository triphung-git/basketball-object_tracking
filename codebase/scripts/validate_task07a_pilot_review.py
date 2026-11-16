#!/usr/bin/env python3
"""Validate a human-reviewed pilot packet without exporting labels or training."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from basketball_scoreboard.dataset_review_validation import validate_pilot_review


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reviewed',required=True);p.add_argument('--source-packet',required=True)
    args=p.parse_args()
    try:
        reviewed=json.loads(Path(args.reviewed).read_text(encoding='utf-8-sig'))
        source=json.loads(Path(args.source_packet).read_text(encoding='utf-8-sig'))
        print(json.dumps(validate_pilot_review(reviewed,source)));sys.exit(0)
    except Exception as error:print('Pilot validation failed ('+type(error).__name__+')',file=sys.stderr);sys.exit(1)
