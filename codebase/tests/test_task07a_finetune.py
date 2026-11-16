"""Protect class mapping and prevent unreviewed labels becoming training negatives."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

SPEC = importlib.util.spec_from_file_location('prepare_task07a_finetune', Path(__file__).resolve().parents[1]/'scripts/prepare_task07a_finetune.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
sys.modules['prepare_task07a_finetune'] = module
TRAIN_SPEC = importlib.util.spec_from_file_location('train_task07a_candidate', Path(__file__).resolve().parents[1]/'scripts/train_task07a_candidate.py')
trainer = importlib.util.module_from_spec(TRAIN_SPEC)
TRAIN_SPEC.loader.exec_module(trainer)


def test_class_order_is_preserved():
    assert module.class_names({2:'rim', 0:'ball', 1:'human'}) == ['ball','human','rim']
    with pytest.raises(ValueError):
        module.class_names(['ball'])
    with pytest.raises(ValueError):
        module.class_names({1:'ball',2:'human',3:'rim'})


@pytest.mark.parametrize('text', ['0 nan 0.5 0.2 0.2', '3 0.5 0.5 0.2 0.2',
                                 '0 0.1 0.5 0.8 0.2', '0 0.5 0.5 0 0.2'])
def test_invalid_yolo_labels_rejected(text):
    with pytest.raises(ValueError):
        module.validate_yolo(text, 3)


def test_draft_is_not_a_negative():
    for state, boxes in [('unreviewed',None), ('unreviewed',[]), ('approved',None)]:
        with pytest.raises(ValueError):
            module.export_row(dict(review_status=state, boxes=boxes, original_wh=[100,100]), ['ball','human','rim'])


def test_export_uses_original_class_order():
    text = module.export_row(dict(review_status='approved', original_wh=[200,100],
                                 boxes=[dict(class_name='human',xyxy=[20,10,60,50])]),
                             ['ball','human','rim'])
    assert text == '1 0.200000000 0.300000000 0.200000000 0.400000000\n'


def test_source_family_catches_roboflow_variants():
    assert module.source_family('89CW1YC6FXUH_jpg.rf.abcdef.jpg') == module.source_family('89CW1YC6FXUH_jpg.rf.123456.jpg')


def staged_fixture(folder):
    import yaml
    names = ['ball','human','rim']
    data = folder/'data.yaml'
    data.write_text(yaml.safe_dump(dict(names=names)))
    checkpoint = folder/'base.pt'
    checkpoint.write_bytes(b'original-checkpoint')
    inventory = []
    for split in ('train','valid','test'):
        image, label = folder/(split+'.jpg'), folder/(split+'.labels.txt')
        image.write_bytes(split.encode())
        label.write_text('0 0.5 0.5 0.2 0.2\n')
        inventory.append(dict(image=str(image), label=str(label), split=split,
                              image_sha256=module.sha256(image), label_sha256=module.sha256(label)))
        (folder/(split+'.txt')).write_text(image.as_posix()+'\n')
    manifest = dict(data_yaml_sha256=module.sha256(data), classes=names,
                    original_inventory=inventory, supplemental=[], quarantined_holdouts=[],
                    counts=dict(train=1,valid=1,test=1), checkpoint=str(checkpoint),
                    checkpoint_sha256=module.sha256(checkpoint))
    (folder/'manifest.json').write_text(json.dumps(manifest))


def test_split_tampering_is_rejected(tmp_path):
    staged_fixture(tmp_path)
    trainer.verify_dataset(tmp_path)
    (tmp_path/'valid.txt').write_text((tmp_path/'train.jpg').as_posix()+'\n')
    with pytest.raises(ValueError, match='split membership'):
        trainer.verify_dataset(tmp_path)


def test_label_tampering_is_rejected(tmp_path):
    staged_fixture(tmp_path)
    (tmp_path/'train.labels.txt').write_text('')
    with pytest.raises(ValueError, match='media/labels changed'):
        trainer.verify_dataset(tmp_path)
