#!/usr/bin/env python3
"""Stage a diagnostic fine-tune dataset; preserve reviewed source packets and runtime.

Only human-approved supplemental rows are exported. Original validation/test
sources shared with original training are quarantined, never moved into train.
This structural audit cannot certify semantic labels or independent-match QA.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from basketball_scoreboard.dataset_review_validation import audit_pilot_draft


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def class_names(value):
    if isinstance(value, dict):
        if sorted(int(key) for key in value) != [0, 1, 2]:
            raise ValueError('Expected contiguous class IDs 0, 1, 2')
        value = [value[key] for key in sorted(value, key=lambda key: int(key))]
    if not isinstance(value, list) or set(value) != {'ball', 'human', 'rim'} or len(value) != 3:
        raise ValueError('Expected exactly ball/human/rim in the original class mapping')
    return value


def validate_yolo(text, count):
    counts = Counter()
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 5:
            raise ValueError('Expected detection labels: class cx cy width height')
        class_id = int(fields[0])
        if fields[0] != str(class_id) or not 0 <= class_id < count:
            raise ValueError('Invalid class ID')
        cx, cy, width, height = map(float, fields[1:])
        if not all(math.isfinite(v) for v in (cx, cy, width, height)):
            raise ValueError('Nonfinite label')
        tolerance = 1e-5
        if not (0 < width <= 1 and 0 < height <= 1 and
                -tolerance <= cx - width / 2 <= cx + width / 2 <= 1 + tolerance and
                -tolerance <= cy - height / 2 <= cy + height / 2 <= 1 + tolerance):
            raise ValueError('Label outside image')
        counts[class_id] += 1
    return counts


def source_family(name):
    # Roboflow adds _jpg.rf.<hash>; unknown augmentation names remain separate.
    name = re.split(r'\.rf\.', Path(name).stem)[0]
    return re.sub(r'_(?:jpg|jpeg|png)$', '', name, flags=re.I)


def export_row(row, names):
    width, height = row['original_wh']
    lines = []
    if row.get('review_status') != 'approved' or not isinstance(row.get('boxes'), list):
        raise ValueError('Only approved non-null labels may be exported')
    for box in row['boxes']:
        x1, y1, x2, y2 = box['xyxy']
        lines.append(f'{names.index(box["class_name"])} {(x1+x2)/2/width:.9f} '
                     f'{(y1+y2)/2/height:.9f} {(x2-x1)/width:.9f} {(y2-y1)/height:.9f}')
    result = '\n'.join(lines) + ('\n' if lines else '')
    validate_yolo(result, len(names))
    return result


def export_supplemental(progress_path, source_path, output, names):
    from PIL import Image
    progress, source = read(progress_path), read(source_path)
    audit = audit_pilot_draft(progress, source)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Supplemental output must be new')
    image_dir, label_dir = output/'images', output/'labels'
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    supplemental = []
    source_root = Path(source_path).resolve().parent
    for row in progress['samples']:
        if row['review_status'] != 'approved':
            continue
        image = (source_root / row['image']).resolve()
        if not image.is_relative_to(source_root):
            raise ValueError('Supplemental image escapes source root')
        if sha256(image) != row['image_sha256']:
            raise ValueError('Supplemental source hash differs: ' + row['sample_id'])
        with Image.open(image) as decoded:
            decoded.load()
            if list(decoded.size) != row['original_wh']:
                raise ValueError('Supplemental dimensions differ')
        destination = image_dir / (row['sample_id'] + image.suffix)
        shutil.copyfile(image, destination)
        label = label_dir / (row['sample_id'] + '.txt')
        label.write_text(export_row(row, names), encoding='utf-8')
        supplemental.append(dict(sample_id=row['sample_id'], source_group=row['source_group'],
                                 image=str(destination), label=str(label),
                                 image_sha256=sha256(destination), label_sha256=sha256(label)))
    report = dict(status='approved_rows_only_staged', classes=names, samples=supplemental,
                  audit=audit, source_sha256=sha256(source_path), progress_sha256=sha256(progress_path),
                  independent_match_test=False, production_promotion_allowed=False)
    (output/'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def prepare(original, progress_path, source_path, checkpoint, output):
    import yaml
    from PIL import Image

    original, output = Path(original).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Output must be a new directory')
    metadata = yaml.safe_load((original / 'data.yaml').read_text(encoding='utf-8-sig'))
    names = class_names(metadata['names'])
    progress, source = read(progress_path), read(source_path)
    audit = audit_pilot_draft(progress, source)
    rows, families, hashes, failures = [], defaultdict(set), defaultdict(set), []
    for split in ('train', 'valid', 'test'):
        images = sorted((original / split / 'images').glob('*'))
        if not images:
            failures.append(f'No images in original {split}')
        for image in images:
            if image.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                continue
            label = original / split / 'labels' / (image.stem + '.txt')
            try:
                if not label.is_file():
                    raise ValueError('Missing label file; cannot assume a negative')
                counts = validate_yolo(label.read_text(), len(names))
                with Image.open(image) as decoded:
                    decoded.load()
                    dimensions = list(decoded.size)
                    pixel_hash = hashlib.sha256(decoded.convert('RGB').tobytes()).hexdigest()
                family = source_family(image.name)
                families[family].add(split)
                hashes[pixel_hash].add(split)
                rows.append(dict(image=str(image), label=str(label), split=split,
                                 source_family=family, pixel_sha256=pixel_hash,
                                 image_sha256=sha256(image), label_sha256=sha256(label),
                                 dimensions=dimensions, class_counts=dict(counts)))
            except (ValueError, OSError) as error:
                failures.append(f'{image.name}: {error}')
    if failures:
        raise ValueError('Original structural QA failed: ' + '; '.join(failures[:20]))

    output.mkdir(parents=True)
    lists = {key: [] for key in ('train', 'valid', 'test')}
    excluded = []
    for row in rows:
        # Preserve exposure history: quarantine holdouts, never reassign training.
        if row['split'] != 'train' and (
                'train' in families[row['source_family']] or 'train' in hashes[row['pixel_sha256']] or
                (row['split'] == 'test' and ('valid' in families[row['source_family']] or
                                            'valid' in hashes[row['pixel_sha256']]))):
            excluded.append(row)
        else:
            lists[row['split']].append(row['image'])
    supplemental = export_supplemental(progress_path, source_path, output/'supplemental', names)['samples']
    lists['train'].extend(row['image'] for row in supplemental)
    if not supplemental or not all(lists.values()):
        raise ValueError('Need approved supplemental rows and nonempty train/valid/test')
    for split, paths in lists.items():
        (output / (split + '.txt')).write_text('\n'.join(Path(p).as_posix() for p in paths) + '\n', encoding='utf-8')
    data = dict(path=output.as_posix(), train=(output/'train.txt').as_posix(),
                val=(output/'valid.txt').as_posix(), test=(output/'test.txt').as_posix(), names=names)
    (output / 'data.yaml').write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    manifest = dict(status='staged_for_QA_not_promoted', original_images=len(rows),
                    counts={k: len(v) for k,v in lists.items()}, classes=names,
                    original_inventory=rows, supplemental=supplemental,
                    quarantined_holdouts=excluded, supplemental_audit=audit,
                    checkpoint=str(Path(checkpoint).resolve()), checkpoint_sha256=sha256(checkpoint),
                    progress_sha256=sha256(progress_path), source_sha256=sha256(source_path),
                    data_yaml_sha256=sha256(output/'data.yaml'),
                    independent_match_test=False, production_promotion_allowed=False,
                    limitations=['Filename-family and exact pixel checks do not detect every near-duplicate.',
                                 'Original semantic label completeness has not been certified.',
                                 'Supplemental source is the development match; it is now training-exposed.',
                                 'OCR/ROI/full-pipeline non-regression must be measured after training.'])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {k: manifest[k] for k in ('status','original_images','counts','classes','limitations')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('progress', 'source', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--original')
    parser.add_argument('--checkpoint')
    parser.add_argument('--supplemental-only', action='store_true')
    args = parser.parse_args()
    if args.supplemental_only:
        from basketball_scoreboard.contracts import CLASS_MAPPING
        report = export_supplemental(args.progress, args.source, args.output, class_names(CLASS_MAPPING))
        print(json.dumps(dict(status=report['status'], approved=len(report['samples']),
                              unreviewed=len(report['audit']['unreviewed_sample_ids']),
                              skipped=len(report['audit']['skipped_sample_ids'])), indent=2))
    else:
        if not args.original or not args.checkpoint:
            parser.error('--original and --checkpoint required unless --supplemental-only')
        print(json.dumps(prepare(args.original, args.progress, args.source, args.checkpoint, args.output), indent=2))
