"""
ml_model.py  (MODIFIED)

What changed compared with the original version
-----------------------------------------------
* The original trained a DecisionTree on `final_training_data.csv`, whose
  labels were produced by a formula over files/insertions/deletions, so the
  model mostly re-learned that formula. It also trained + printed at import.
* v2 (default): RandomForest trained on `mined_training_data.csv`, built
  from REAL history with SZZ-lite labels (see mine_history.py).
  Evaluated chronologically (train on the past, test on the future) against
  two baselines, so the claim "function-level features help" is measurable.
* The original DecisionTree path is kept as an automatic fallback
  (`predict_risk`, unchanged signature) so nothing that used it breaks.
* Training happens lazily / via `python ml_model.py`, never on import.

Risk bands are RELATIVE: among commits that change Python functions,
HIGH = the riskiest ~15%, MEDIUM = the next ~25%, LOW = the rest. Scores are model scores, not
guaranteed probabilities.

Test failures are a hard rule (any failing relevant test => HIGH), because
they cannot be mined for thousands of historical commits.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from commit_features import KAMEI_FEATURES

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "mined_training_data.csv")
MODEL_PATH = os.path.join(HERE, "model_v2.joblib")
REPORT_PATH = os.path.join(HERE, "model_report.json")

# The test-gap features are reported to the user but deliberately NOT model
# inputs: in our ablation they did not improve held-out accuracy.
MODEL_FEATURES = KAMEI_FEATURES + [
    "functions_changed", "affected_files", "blast_radius",
]
BASELINES = {
    "lines changed only": ["insertions", "deletions"],
    "Kamei-style change metrics": KAMEI_FEATURES,
}

HIGH_PCT, MEDIUM_PCT = 85, 60        # percentile cut-offs of the model score


def _forest(seed=0):
    return RandomForestClassifier(
        n_estimators=300, min_samples_leaf=5,
        random_state=seed, n_jobs=-1)


# ------------------------------------------------------------------
# Training and evaluation
# ------------------------------------------------------------------

def load_data(path=DATA_PATH):
    data = pd.read_csv(path)
    return data.sort_values("date").reset_index(drop=True)


def recall_at_top(y, score, fraction=0.2):
    k = max(1, int(len(y) * fraction))
    top = np.argsort(-score)[:k]
    return float(np.sum(np.asarray(y)[top]) / max(np.sum(y), 1))


def chronological_cv(data, features, seeds=(0, 1, 2)):
    """Expanding-window evaluation: always train on the past, test on the future."""
    n, y = len(data), data["defect_inducing"].values
    rows = []
    for lo, hi in [(.40, .55), (.55, .70), (.70, .85), (.85, 1.0)]:
        s, e = int(n * lo), int(n * hi)
        if y[:s].sum() == 0 or y[s:e].sum() == 0:
            continue
        for seed in seeds:
            m = _forest(seed).fit(data.loc[:s - 1, features], y[:s])
            p = m.predict_proba(data.loc[s:e - 1, features])[:, 1]
            rows.append((roc_auc_score(y[s:e], p),
                         average_precision_score(y[s:e], p),
                         recall_at_top(y[s:e], p, 0.2)))
    auc, ap, rec = np.mean(rows, axis=0)
    return {"roc_auc": round(float(auc), 3),
            "pr_auc": round(float(ap), 3),
            "recall_at_top20pct": round(float(rec), 3)}


def leave_one_repo_out(data, features):
    """Train on all repos but one, test on the unseen repo (generalisation)."""
    y = data["defect_inducing"].values
    out = {}
    for repo in sorted(data["repo"].unique()):
        te = (data["repo"] == repo).values
        if y[~te].sum() == 0 or y[te].sum() == 0:
            continue
        m = _forest().fit(data.loc[~te, features], y[~te])
        p = m.predict_proba(data.loc[te, features])[:, 1]
        out[repo] = {"roc_auc": round(float(roc_auc_score(y[te], p)), 3),
                     "recall_at_top20pct": round(recall_at_top(y[te], p, 0.2), 3)}
    return out


def train(verbose=True, data_path=DATA_PATH, evaluate=True):
    data = load_data(data_path)
    y = data["defect_inducing"].values

    report = {
        "rows": int(len(data)),
        "repos": sorted(data["repo"].unique().tolist()),
        "defect_rate": round(float(y.mean()), 4),
        "features": MODEL_FEATURES,
        "chronological_cv": {},
    }
    report["leave_one_repo_out"] = {}
    if evaluate:
        for name, feats in BASELINES.items():
            report["chronological_cv"][name] = chronological_cv(data, feats)
        report["chronological_cv"]["this project (+ function-level)"] = (
            chronological_cv(data, MODEL_FEATURES))
        report["leave_one_repo_out"] = {
            "baseline (Kamei-style)": leave_one_repo_out(data, KAMEI_FEATURES),
            "this project": leave_one_repo_out(data, MODEL_FEATURES),
        }

    # score thresholds from out-of-fold predictions on all rows
    X = data[MODEL_FEATURES]
    oof = cross_val_predict(
        _forest(), X, y,
        cv=StratifiedKFold(5, shuffle=True, random_state=0),
        method="predict_proba")[:, 1]
    # bands are defined among commits that actually change Python functions
    # (docs / config-only commits would otherwise stretch the scale)
    code_only = oof[(data["functions_changed"] > 0).values]
    thresholds = {
        "medium": float(np.percentile(code_only, MEDIUM_PCT)),
        "high": float(np.percentile(code_only, HIGH_PCT)),
    }
    report["thresholds"] = thresholds

    model = _forest().fit(X, y)
    bundle = {
        "model": model,
        "features": MODEL_FEATURES,
        "thresholds": thresholds,
        "medians": X.median().to_dict(),
        "base_rate": float(y.mean()),
        "report": report,
    }
    joblib.dump(bundle, MODEL_PATH)
    if evaluate:
        with open(REPORT_PATH, "w") as fh:
            json.dump(report, fh, indent=2)

    if verbose and evaluate:
        print("\n===================================")
        print("       ML MODEL EVALUATION (v2)")
        print("===================================")
        print(f"Training commits : {report['rows']}  "
              f"from {', '.join(report['repos'])}")
        print(f"Defect-inducing  : {report['defect_rate'] * 100:.1f}%")
        print("\nChronological validation (train on past, test on future)")
        print(f"{'model':36s}{'ROC-AUC':>9s}{'PR-AUC':>9s}{'Recall@20%':>12s}")
        for name, m in report["chronological_cv"].items():
            print(f"{name:36s}{m['roc_auc']:>9.3f}{m['pr_auc']:>9.3f}"
                  f"{m['recall_at_top20pct']:>12.3f}")
        print("\nLeave-one-repo-out (test on a repo the model never saw)")
        print(f"{'held-out repo':16s}{'baseline AUC':>14s}{'ours AUC':>10s}"
              f"{'ours Recall@20%':>17s}")
        base = report["leave_one_repo_out"]["baseline (Kamei-style)"]
        ours = report["leave_one_repo_out"]["this project"]
        for r in ours:
            print(f"{r:16s}{base[r]['roc_auc']:>14.3f}{ours[r]['roc_auc']:>10.3f}"
                  f"{ours[r]['recall_at_top20pct']:>17.3f}")
        print("\nSaved:", os.path.basename(MODEL_PATH))
    return bundle


_BUNDLE = None


def _get_bundle():
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE
    try:
        _BUNDLE = joblib.load(MODEL_PATH)
    except Exception:
        if os.path.exists(DATA_PATH):
            _BUNDLE = train(verbose=False, evaluate=False)
        else:
            _BUNDLE = False
    return _BUNDLE


# ------------------------------------------------------------------
# Prediction + explanation
# ------------------------------------------------------------------

def _band(score, thresholds):
    if score >= thresholds["high"]:
        return "HIGH"
    if score >= thresholds["medium"]:
        return "MEDIUM"
    return "LOW"


def score_change(features, test_failures=0):
    """
    features: dict from commit_features.extract_features().
    Returns dict(level, score, model, contributions, notes).
    """
    bundle = _get_bundle()
    if not bundle:                                      # no mined data -> original model
        level, conf = predict_risk(
            features["files_changed"], features["insertions"],
            features["deletions"], features["affected_files"],
            features["functions_changed"], test_failures)
        return {"level": level, "score": conf, "model": "legacy",
                "contributions": [], "notes": []}

    cols = bundle["features"]
    row = pd.DataFrame([[features[c] for c in cols]], columns=cols)
    score = float(bundle["model"].predict_proba(row)[0, 1])
    level = _band(score, bundle["thresholds"])

    # local explanation: replace each feature by its training median and
    # see how much the score drops (model-agnostic, no extra dependency)
    contributions = []
    for c in cols:
        alt = row.copy()
        alt[c] = bundle["medians"][c]
        delta = score - float(bundle["model"].predict_proba(alt)[0, 1])
        if abs(delta) >= 0.005:
            contributions.append((c, features[c], round(delta, 3)))
    contributions.sort(key=lambda t: -abs(t[2]))

    notes = []
    if test_failures > 0 and level != "HIGH":
        notes.append("Raised to HIGH because relevant tests failed.")
        level = "HIGH"

    return {"level": level, "score": score, "model": "v2",
            "base_rate": bundle["base_rate"],
            "contributions": contributions[:4], "notes": notes}


# ------------------------------------------------------------------
# ORIGINAL model (kept as fallback; signature unchanged)
# ------------------------------------------------------------------

_LEGACY = None


def _legacy_model():
    global _LEGACY
    if _LEGACY is None:
        from sklearn.tree import DecisionTreeClassifier
        data = pd.read_csv(os.path.join(HERE, "final_training_data.csv"))
        cols = ["files_changed", "insertions", "deletions",
                "affected_files", "functions_changed", "test_failures"]
        _LEGACY = DecisionTreeClassifier(max_depth=4, random_state=42).fit(
            data[cols], data["risk"])
    return _LEGACY


def predict_risk(files_changed, insertions, deletions, affected_files,
                 functions_changed, test_failures):
    model = _legacy_model()
    cols = ["files_changed", "insertions", "deletions",
            "affected_files", "functions_changed", "test_failures"]
    row = pd.DataFrame([[files_changed, insertions, deletions, affected_files,
                         functions_changed, test_failures]], columns=cols)
    prediction = model.predict(row)[0]
    probs = dict(zip(model.classes_, model.predict_proba(row)[0]))
    return prediction, probs.get(prediction, 0)


if __name__ == "__main__":
    train(verbose=True)
