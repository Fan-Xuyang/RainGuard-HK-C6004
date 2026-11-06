"""Independently reconcile M3 summary metrics with saved row-level predictions."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import joblib
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dataset-dir', type=Path, default=root / 'datasets/RainGuard_HK_Dataset')
parser.add_argument('--results-dir', type=Path, default=root / 'runtime/m3-evaluation')
args = parser.parse_args()
extended = json.loads((args.results_dir / 'm3_extended_results.json').read_text(encoding='utf-8'))
published = json.loads((root / 'docs/m3/m3_extended_results.json').read_text(encoding='utf-8'))
original = json.loads((root / 'docs/m3/project_experiments_original.json').read_text(encoding='utf-8'))
rerun = json.loads((root / 'docs/m3/project_experiments_rerun.json').read_text(encoding='utf-8'))
with (args.results_dir / 'm3_predictions.csv').open(encoding='utf-8-sig', newline='') as f:
    predictions = list(csv.DictReader(f))
keys = [(r['station'], r['split'], r['target_date'], r['method']) for r in predictions]
assert len(keys) == len(set(keys)) == 21161
groups = defaultdict(list)
for r in predictions:
    groups[(r['station'], r['method'], r['split'])].append(r)
records = {(x['station'], x['method'], x['period']): x for x in extended['records']}
published_records = {(x['station'], x['method'], x['period']): x for x in published['records']}
assert extended['source_hashes'] == published['source_hashes']
assert records.keys() == published_records.keys()
for key, summary in records.items():
    reference = published_records[key]
    assert summary.keys() == reference.keys()
    for metric, value in summary.items():
        expected = reference[metric]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            assert isinstance(expected, (int, float)) and abs(value - expected) < 1e-10, (key, metric)
        else:
            assert value == expected, (key, metric)
assert len(groups) == 3 * 7 * 2
for key, group in groups.items():
    summary = records[key]
    y = np.asarray([int(r['label']) for r in group])
    p = np.asarray([float(r['probability']) for r in group])
    pred = np.asarray([int(r['predicted']) for r in group])
    assert all(float(r['threshold']) == summary['threshold'] for r in group)
    assert np.array_equal(pred, p >= summary['threshold'])
    assert len(y) == summary['n'] and int(y.sum()) == summary['positive']
    assert all(int(r['label']) == (float(r['actual_mm']) >= 25) for r in group)
    recalculated = {
        'average_precision': average_precision_score(y, p), 'roc_auc': roc_auc_score(y, p),
        'brier': brier_score_loss(y, p), 'precision': precision_score(y, pred, zero_division=0),
        'recall': recall_score(y, pred, zero_division=0), 'f1': f1_score(y, pred, zero_division=0),
    }
    for metric, value in recalculated.items():
        assert abs(summary[metric] - value) < 1e-12, (key, metric)
    assert confusion_matrix(y, pred, labels=[0, 1]).ravel().tolist() == [
        summary[x] for x in ('tn', 'fp', 'fn', 'tp')]
for station in ('HKO', 'LFS', 'SHA'):
    for method in extended['methods']:
        assert records[(station, method, 'test')]['threshold'] == records[(station, method, 'holdout_2026_onward')]['threshold']

def identify(x):
    return (x['trace_policy'], x['station'], x['model'])
a = {identify(x): x for x in original['results']}
b = {identify(x): x for x in rerun['results']}
assert len(a) == len(b) == 30 and a.keys() == b.keys()
max_difference = 0.0
for key, old in a.items():
    new = b[key]
    assert old['threshold'] == new['threshold']
    for split in ('validation', 'test'):
        assert old[split]['confusion_tn_fp_fn_tp'] == new[split]['confusion_tn_fp_fn_tp']
        for metric in ('average_precision', 'roc_auc', 'brier', 'precision', 'recall', 'f1'):
            max_difference = max(max_difference, abs(old[split][metric] - new[split][metric]))
    if key[0] == 'exclude':
        m = records[(key[1], key[2], 'test')]
        assert m['threshold'] == new['threshold']
        assert [m[t] for t in ('tn', 'fp', 'fn', 'tp')] == new['test']['confusion_tn_fp_fn_tp']
        for metric in ('average_precision', 'roc_auc', 'brier', 'precision', 'recall', 'f1'):
            assert abs(m[metric] - new['test'][metric]) < 1e-12
assert max_difference < 1e-12
features = extended['features']
for station in ('HKO', 'LFS', 'SHA'):
    models = joblib.load(args.results_dir / f'models_{station}.joblib')
    assert set(models) == {'logistic_regression', 'random_forest'}
    for split in ('test', 'holdout_2026_onward'):
        path = args.dataset_dir / f'training/trace_exclude/{split}.csv'
        with path.open(encoding='utf-8-sig', newline='') as f:
            input_rows = sorted((r for r in csv.DictReader(f) if r['station'] == station),
                                key=lambda r: r['target_date'])
        inputs = np.asarray([[float(r[c]) for c in features] for r in input_rows])
        for method, model in models.items():
            expected = {r['target_date']: float(r['probability'])
                        for r in groups[(station, method, split)]}
            restored = model.predict_proba(inputs)[:, 1]
            assert np.allclose(restored, [expected[r['target_date']] for r in input_rows],
                               rtol=0, atol=1e-12), (station, split, method)
print(f'PASS: {len(predictions)} predictions in {len(groups)} groups reconcile to saved metrics.')
print('PASS: generated records and source hashes match the published M3 summary.')
print(f'PASS: {len(a)} original experiments match rerun; max metric difference {max_difference:.3g}.')
print('PASS: 15 main-policy test rows match the independent extension; thresholds remain fixed for 2026.')
print('PASS: all six saved model artifacts reproduce their test and 2026 probabilities.')
