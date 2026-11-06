"""M3 reproducible extension of the frozen RainGuard-HK model experiment.

Uses the dataset's split files; never changes the project source or dataset.
The 2026 holdout is evaluated with the same train-only fits and validation-only
thresholds as the 2023-25 test, including a new two-state empirical baseline.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import platform
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets/RainGuard_HK_Dataset/training"
OUT = ROOT / "runtime/m3-evaluation"
FEATURES = ["log1p_lag1", "log1p_lag2", "log1p_lag3", "log1p_past7_total",
            "past7_wetdays", "sin_dayofyear", "cos_dayofyear"]
SPLITS = ["train", "validation", "test", "holdout_2026_onward"]
PERIODS = {
    "train": ("2000-01-01", "2019-12-31"),
    "validation": ("2020-01-01", "2022-12-31"),
    "test": ("2023-01-01", "2025-12-31"),
    "holdout_2026_onward": ("2026-01-01", "2026-12-31"),
}
METHODS = ["train_prevalence", "train_prevalence_lower_threshold", "seasonal_prevalence", "persistence",
           "prior_day_conditional", "logistic_regression", "random_forest"]
THRESHOLDS = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
RF_PARAMS = {"n_estimators": 120, "max_depth": 8,
             "min_samples_leaf": 10, "random_state": 42, "n_jobs": 2}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def measure(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    pred = p >= threshold
    both_classes = len(np.unique(y)) == 2
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel().tolist()
    return {
        "n": int(len(y)), "positive": int(y.sum()),
        "prevalence": float(y.mean()),
        "average_precision": float(average_precision_score(y, p)) if y.sum() else None,
        "roc_auc": float(roc_auc_score(y, p)) if both_classes else None,
        "brier": float(brier_score_loss(y, p)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def paired_ap_month_block_ci(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray,
                             dates: list[str], seed: int, draws: int = 1500) -> dict:
    """Resample year-month blocks, stratified by calendar month.

    This describes conditional test-sample uncertainty for already-fitted
    models, not variation from retraining or a guarantee of causal significance.
    """
    blocks = defaultdict(list)
    for i, date in enumerate(dates):
        blocks[(int(date[:4]), int(date[5:7]))].append(i)
    by_month = {m: [np.asarray(blocks[(year, month)], dtype=int)
                    for year, month in sorted(blocks) if month == m]
                for m in range(1, 13)}
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(draws):
        indices = []
        for candidates in by_month.values():
            if candidates:
                for choice in rng.integers(0, len(candidates), size=len(candidates)):
                    indices.extend(candidates[int(choice)])
        ix = np.asarray(indices, dtype=int)
        if len(np.unique(y[ix])) < 2:
            continue
        diffs.append(average_precision_score(y[ix], p_a[ix]) -
                     average_precision_score(y[ix], p_b[ix]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"point": float(average_precision_score(y, p_a) - average_precision_score(y, p_b)),
            "ci95_low": float(lo), "ci95_high": float(hi),
            "draws": draws, "valid_draws": len(diffs),
            "block_count": len(blocks), "seed": seed}


def main() -> None:
    global DATA, OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path,
                        default=ROOT / "datasets/RainGuard_HK_Dataset",
                        help="Path to the verified v0.1.0 RainGuard_HK_Dataset folder")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runtime/m3-evaluation",
                        help="Output directory for results and predictions")
    args = parser.parse_args()
    DATA = args.dataset_dir.resolve() / "training"
    OUT = args.output_dir.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    files = {s: DATA / "trace_exclude" / f"{s}.csv" for s in SPLITS}
    rows = {s: read_csv(path) for s, path in files.items()}
    aggregate = read_csv(DATA / "core_features_trace_exclude.csv")
    seen = set()
    for split, group in rows.items():
        expected = [r for r in aggregate if r["split"] == split]
        key = lambda r: (r["station"], r["target_date"])
        assert sorted(group, key=key) == sorted(expected, key=key), split
        for r in group:
            k = (r["station"], r["target_date"])
            assert k not in seen, f"duplicate {k}"
            seen.add(k)
            assert r["split"] == split and r["trace_policy"] == "exclude"
            assert PERIODS[split][0] <= r["target_date"] <= PERIODS[split][1]
            assert (dt.date.fromisoformat(r["target_date"]) -
                    dt.date.fromisoformat(r["feature_asof_date"])).days == 1
            assert all(np.isfinite(float(r[f])) for f in FEATURES)
            assert int(r["target_ge25mm"]) == int(float(r["target_rainfall_mm"]) >= 25)

    results = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "protocol_reference_commit": "62b30afd1b6331b493e627bc047615ceba2fe389",
        "trace_policy": "exclude",
        "features": FEATURES,
        "periods": PERIODS,
        "source_hashes": {str(p.relative_to(DATA)).replace("\\", "/"): digest(p)
                          for p in [DATA / "core_features_trace_exclude.csv", *files.values()]},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
                     "joblib": joblib.__version__},
        "methods": METHODS, "threshold_candidates": THRESHOLDS,
        "rf_parameters": RF_PARAMS,
        "prior_day_conditional_definition":
            "Training-set event rate conditional on previous-day rainfall >=25 mm; no smoothing.",
        "lower_threshold_baseline_definition":
            "Same train-prevalence probability; validation F1 selects from [0] plus the original threshold grid.",
        "bootstrap_definition":
            "1500 paired year-month block resamples stratified by calendar month; fixed fitted models; seed 20261106.",
        "records": [], "bootstrap": [], "conditional_training_rates": {},
    }
    prediction_rows = []
    for station in ["HKO", "LFS", "SHA"]:
        groups = {s: sorted((r for r in rows[s] if r["station"] == station),
                            key=lambda r: r["target_date"]) for s in SPLITS}
        X = {s: np.asarray([[float(r[f]) for f in FEATURES] for r in g])
             for s, g in groups.items()}
        y = {s: np.asarray([int(r["target_ge25mm"]) for r in g])
             for s, g in groups.items()}
        lag = {s: np.asarray([int(float(r["lag1_rainfall_mm"]) >= 25)
                              for r in g]) for s, g in groups.items()}
        assert all(len(np.unique(y[s])) == 2 for s in SPLITS)
        train_prevalence = float(y["train"].mean())
        month_rates = {m: float(np.mean([int(r["target_ge25mm"]) for r in groups["train"]
                                         if int(r["target_date"][5:7]) == m]))
                       for m in range(1, 13)}
        conditional_rates = {state: float(y["train"][lag["train"] == state].mean())
                             for state in [0, 1]}
        results["conditional_training_rates"][station] = {
            str(state): {"n": int((lag["train"] == state).sum()),
                         "positive_rate": conditional_rates[state]} for state in [0, 1]}
        eval_splits = ["validation", "test", "holdout_2026_onward"]
        probs = {
            "train_prevalence": {s: np.full(len(y[s]), train_prevalence) for s in eval_splits},
            "train_prevalence_lower_threshold": {s: np.full(len(y[s]), train_prevalence)
                                                 for s in eval_splits},
            "seasonal_prevalence": {s: np.asarray([month_rates[int(r["target_date"][5:7])]
                                                   for r in groups[s]]) for s in eval_splits},
            "persistence": {s: lag[s].astype(float) for s in eval_splits},
            "prior_day_conditional": {s: np.asarray([conditional_rates[z] for z in lag[s]])
                                      for s in eval_splits},
        }
        models = {
            "logistic_regression": make_pipeline(StandardScaler(),
                LogisticRegression(C=1, max_iter=2000, random_state=42)),
            "random_forest": RandomForestClassifier(**RF_PARAMS),
        }
        for name, model in models.items():
            model.fit(X["train"], y["train"])
            probs[name] = {s: model.predict_proba(X[s])[:, 1] for s in eval_splits}
        joblib.dump(models, OUT / f"models_{station}.joblib")
        for name in METHODS:
            candidates = [0.0] + THRESHOLDS if name == "train_prevalence_lower_threshold" else THRESHOLDS
            threshold = (0.5 if name == "persistence" else
                         max(candidates, key=lambda t: f1_score(y["validation"],
                             probs[name]["validation"] >= t, zero_division=0)))
            for split in eval_splits:
                indices = {split: np.ones(len(y[split]), dtype=bool)}
                if split == "test":
                    for year in [2023, 2024, 2025]:
                        indices[str(year)] = np.asarray([r["target_date"].startswith(str(year))
                                                        for r in groups[split]])
                    indices["test_jan_aug"] = np.asarray([int(r["target_date"][5:7]) <= 8
                                                          for r in groups[split]])
                for period, ix in indices.items():
                    m = measure(y[split][ix], probs[name][split][ix], threshold)
                    results["records"].append({"station": station, "method": name,
                                               "period": period, "threshold": threshold, **m})
                if split in ["test", "holdout_2026_onward"]:
                    for r, prob in zip(groups[split], probs[name][split]):
                        prediction_rows.append({"station": station, "split": split,
                            "target_date": r["target_date"], "actual_mm": r["target_rainfall_mm"],
                            "label": r["target_ge25mm"], "method": name,
                            "probability": float(prob), "threshold": threshold,
                            "predicted": int(prob >= threshold)})
        test_dates = [r["target_date"] for r in groups["test"]]
        for a, b in [("logistic_regression", "seasonal_prevalence"),
                     ("random_forest", "logistic_regression")]:
            ci = paired_ap_month_block_ci(y["test"], probs[a]["test"], probs[b]["test"],
                                          test_dates, seed=20261106)
            results["bootstrap"].append({"station": station, "comparison": f"{a} - {b}", **ci})
        print(station, "completed", flush=True)

    output = OUT / "m3_extended_results.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUT / "m3_predictions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(prediction_rows[0]))
        writer.writeheader()
        writer.writerows(prediction_rows)
    print("Saved", output, "and predictions", flush=True)


if __name__ == "__main__":
    main()
