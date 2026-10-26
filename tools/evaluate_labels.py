"""Evaluate endpoint labels. Ground truth is never consumed by the analyzer."""

import argparse
import json
from pathlib import Path


def evaluate(report, truth):
    predictions = {}
    rank = {"covered": 0, "needs_review": 1, "suspected": 2}
    for result in report["results"]:
        key = tuple(result["endpoint"])
        status = result["status"]
        if key not in predictions or rank[status] > rank[predictions[key]]:
            predictions[key] = status
    counts = {
        "tp": 0,
        "fp": 0,
        "tn": 0,
        "fn": 0,
        "needs_review_or_missing": 0,
        "unresolved_negative": 0,
    }
    rows = []
    for case in truth:
        predicted = predictions.get((case["method"], case["route"]), "missing")
        positive = case["status"] == "suspected"
        detected = predicted == "suspected"
        counts[
            "tp"
            if positive and detected
            else "fn"
            if positive
            else "fp"
            if detected
            else "tn"
            if predicted == "covered"
            else "unresolved_negative"
        ] += 1
        counts["needs_review_or_missing"] += predicted in ("needs_review", "missing")
        rows.append(
            {
                "endpoint": [case["method"], case["route"]],
                "expected": case["status"],
                "observed": predicted,
            }
        )
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    counts.update(
        {
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        }
    )
    return {"sample_type": "provided_labels", "counts": counts, "rows": rows}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("analysis", type=Path)
    p.add_argument("truth", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = evaluate(
        json.loads(a.analysis.read_text(encoding="utf-8")),
        json.loads(a.truth.read_text(encoding="utf-8")),
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
