#!/usr/bin/env python3
"""Train an isolated experimental candidate from a verified Roboflow checkpoint.

Does not change the application's approved model, OCR, ROI, or configurations.
Evaluation on the training-exposed development match cannot authorize promotion.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from prepare_task07a_finetune import ROOT, class_names, read, sha256


def runtime_snapshot():
    paths = [p for directory in (ROOT/'src', ROOT/'configs')
             for p in sorted(directory.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts]
    paths.extend(sorted((ROOT/'.model-cache').rglob('*.onnx')))
    return {str(p.relative_to(ROOT)): sha256(p) for p in paths}


def verify_dataset(folder):
    import yaml
    folder = Path(folder).resolve()
    manifest = read(folder/'manifest.json')
    if sha256(folder/'data.yaml') != manifest['data_yaml_sha256']:
        raise ValueError('Dataset configuration changed since preparation')
    data = yaml.safe_load((folder/'data.yaml').read_text())
    names = class_names(data['names'])
    if names != manifest['classes']:
        raise ValueError('Dataset class order changed')
    for row in manifest['original_inventory'] + manifest['supplemental']:
        for key in ('image', 'label'):
            if sha256(row[key]) != row[key+'_sha256']:
                raise ValueError('Dataset media/labels changed: ' + row[key])
    expected = {key: [] for key in ('train','valid','test')}
    excluded = {row['image'] for row in manifest['quarantined_holdouts']}
    for row in manifest['original_inventory']:
        if row['image'] not in excluded:
            expected[row['split']].append(row['image'])
    expected['train'].extend(row['image'] for row in manifest['supplemental'])
    for split, rows in expected.items():
        actual = (folder/(split+'.txt')).read_text().splitlines()
        if actual != [Path(p).as_posix() for p in rows] or len(rows) != manifest['counts'][split]:
            raise ValueError('Dataset split membership changed')
    checkpoint = Path(manifest['checkpoint'])
    if sha256(checkpoint) != manifest['checkpoint_sha256']:
        raise ValueError('Original checkpoint differs')
    return manifest, names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch', type=int, default=2)
    parser.add_argument('--patience', type=int, default=10)
    parser.add_argument('--name', default='candidate', help='Subdirectory name for weights and plots')
    parser.add_argument('--execute', action='store_true', help='Run the experimental fine-tune')
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100 or not 1 <= args.batch <= 8:
        raise ValueError('Expected epochs 1..100, batch 1..8 for this run')
    manifest, names = verify_dataset(args.dataset)
    import torch
    import ultralytics
    from ultralytics import YOLO

    model = YOLO(manifest['checkpoint'])
    actual_names = class_names(model.names)
    if actual_names != names:
        raise ValueError('Original checkpoint class order differs from dataset')

    before = runtime_snapshot()
    output = Path(args.output).resolve()
    if output.exists() and (output / 'run.json').exists():
        raise ValueError('Output directory already contains a run.json; choose a new output path')
    output.mkdir(parents=True, exist_ok=True)

    report = dict(
        status='preflight_passed',
        created_utc=datetime.now(timezone.utc).isoformat(),
        checkpoint=manifest['checkpoint'],
        checkpoint_sha256=manifest['checkpoint_sha256'],
        classes=names,
        torch=torch.__version__,
        ultralytics=ultralytics.__version__,
        cuda_available=torch.cuda.is_available(),
        dataset_counts=manifest['counts'],
        runtime_sha256=before,
        independent_match_test=False,
        production_promotion_allowed=False,
        epochs=args.epochs,
        batch=args.batch,
        patience=args.patience,
        recipe=dict(
            imgsz=640,
            optimizer='AdamW',
            lr0=0.0001,
            seed=7,
            deterministic=True,
            workers=0,
            cache=False,
            device=0,
        ),
        limitations=manifest['limitations'],
    )

    if not args.execute:
        print(json.dumps(report, indent=2))
        return 0

    if not torch.cuda.is_available():
        raise ValueError('CUDA training environment required; refusing an unbounded CPU run')

    output.mkdir(parents=True, exist_ok=True)
    report['status'] = 'training'
    report_path = output / 'run.json'
    heartbeat_path = output / 'heartbeat.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def write_heartbeat(stage, **extra):
        hb = dict(
            pid=os.getpid(),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            status=stage,
            epochs_target=args.epochs,
            batch_size=args.batch,
            **extra,
        )
        tmp = heartbeat_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(hb, indent=2), encoding='utf-8')
        tmp.replace(heartbeat_path)

    write_heartbeat('training_started', epoch=0)

    # Attach atomic callbacks for heartbeat and monitoring
    def on_train_epoch_end(trainer):
        ep = trainer.epoch + 1
        eps = trainer.epochs
        peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
        fitness = float(trainer.fitness) if getattr(trainer, 'fitness', None) is not None else None
        write_heartbeat(
            'epoch_completed',
            epoch=ep,
            total_epochs=eps,
            progress_pct=round(100.0 * ep / eps, 2),
            fitness=fitness,
            peak_vram_mb=round(peak_vram, 2),
            best_checkpoint=str(output / args.name / 'weights/best.pt'),
            last_checkpoint=str(output / args.name / 'weights/last.pt'),
        )

    batch_counter = [0]

    def on_train_batch_end(trainer):
        batch_counter[0] += 1
        if batch_counter[0] % 100 == 0:
            ep = trainer.epoch + 1
            eps = trainer.epochs
            peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
            write_heartbeat(
                'batch_progress',
                epoch=ep,
                total_epochs=eps,
                batch_step=batch_counter[0],
                peak_vram_mb=round(peak_vram, 2),
            )

    model.add_callback('on_train_epoch_end', on_train_epoch_end)
    model.add_callback('on_train_batch_end', on_train_batch_end)

    try:
        model.train(
            data=str(Path(args.dataset).resolve() / 'data.yaml'),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=640,
            device=0,
            workers=0,
            cache=False,
            optimizer='AdamW',
            lr0=0.0001,
            seed=7,
            deterministic=True,
            patience=args.patience,
            resume=False,
            project=str(output),
            name=args.name,
            exist_ok=False,
            plots=True,
        )

        best_weights = output / args.name / 'weights/best.pt'
        last_weights = output / args.name / 'weights/last.pt'
        results_csv = output / args.name / 'results.csv'

        if not best_weights.exists():
            raise RuntimeError(f'Expected best checkpoint not found at {best_weights}')

        # Verify checkpoint reloadability
        reloaded = YOLO(str(best_weights))
        reloaded_classes = class_names(reloaded.names)
        if reloaded_classes != names:
            raise ValueError(f'Reloaded checkpoint class names mismatch: {reloaded_classes}')

        report['status'] = 'trained_pending_pipeline_evaluation'
        report['best_checkpoint'] = str(best_weights)
        report['best_checkpoint_sha256'] = sha256(best_weights)
        if last_weights.exists():
            report['last_checkpoint'] = str(last_weights)
            report['last_checkpoint_sha256'] = sha256(last_weights)

        if results_csv.exists():
            lines = results_csv.read_text(encoding='utf-8', errors='ignore').strip().splitlines()
            if len(lines) >= 2:
                header = [h.strip() for h in lines[0].split(',')]
                final_metrics = [v.strip() for v in lines[-1].split(',')]
                report['final_epoch_metrics'] = dict(zip(header, final_metrics))

        write_heartbeat(
            'training_completed',
            best_checkpoint=str(best_weights),
            best_checkpoint_sha256=report['best_checkpoint_sha256'],
        )

    except KeyboardInterrupt:
        report['status'] = 'interrupted'
        report['error_type'] = 'KeyboardInterrupt'
        write_heartbeat('interrupted', error='KeyboardInterrupt')
        raise
    except Exception as error:
        report['status'] = 'training_failed'
        report['error_type'] = type(error).__name__
        report['error_message'] = str(error)
        write_heartbeat('failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['completed_utc'] = datetime.now(timezone.utc).isoformat()
        report['runtime_unchanged'] = runtime_snapshot() == before
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        if not report['runtime_unchanged']:
            raise RuntimeError('Application sources/configurations changed during training')

    return 0


if __name__ == '__main__':
    sys.exit(main())
