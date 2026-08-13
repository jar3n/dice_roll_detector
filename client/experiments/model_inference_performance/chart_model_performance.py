#!/usr/bin/env python3
"""
    Generate comparison charts (inference time, accuracy, confidence)
    for the models logged in the predictions CSV.

    Usage:
        python plot_model_comparison.py /path/to/predictions.csv [output.png]

    If no path is given, it looks for "predictions.csv" in the
    current working directory. If no output path is given, the chart
    is saved next to the CSV as "<csv_stem>_comparison.png".

    Requires matplotlib:
        pip install matplotlib
"""

import csv
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


def _to_float_or_none(value: str):
    value = (value or "").strip()
    if value == "" or value.lower() == "none":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_rows(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def discover_model_names(fieldnames: list[str]) -> list[str]:
    """Find model names from columns like '<model>_predicted'."""
    models = []
    for name in fieldnames:
        if name.endswith("_predicted"):
            models.append(name[: -len("_predicted")])
    return models


def collect_model_data(rows: list[dict], model: str) -> dict:
    """Pull the raw per-row values needed for plotting, for one model."""
    inference_times = []
    confidences = []
    total = len(rows)
    detections = 0
    correct = 0

    predicted_col = f"{model}_predicted"
    confidence_col = f"{model}_confidence"
    correct_col = f"{model}_correct"
    inference_col = f"{model}_inference_ms"

    for row in rows:
        predicted = (row.get(predicted_col) or "").strip()
        has_detection = predicted != "" and predicted.lower() != "none"

        if has_detection:
            detections += 1
            conf = _to_float_or_none(row.get(confidence_col))
            if conf is not None:
                confidences.append(conf)

        if correct_col in row and _to_bool(row.get(correct_col)):
            correct += 1

        inf_ms = _to_float_or_none(row.get(inference_col))
        if inf_ms is not None:
            inference_times.append(inf_ms)

    return {
        "model": model,
        "inference_times": inference_times,
        "confidences": confidences,
        "accuracy_overall": (correct / total) if total else 0.0,
        "accuracy_when_detected": (correct / detections) if detections else 0.0,
        "detection_rate": (detections / total) if total else 0.0,
    }


def make_charts(rows: list[dict], models: list[str], out_path: Path):
    data = {m: collect_model_data(rows, m) for m in models}
    colors = plt.cm.tab10.colors

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Model Comparison", fontsize=15, fontweight="bold")

    # --- 1. Bar chart: average inference time, with std-dev error bars ---
    ax = axes[0]
    avg_times = [
        statistics.mean(data[m]["inference_times"]) if data[m]["inference_times"] else 0
        for m in models
    ]
    std_times = [
        statistics.pstdev(data[m]["inference_times"])
        if len(data[m]["inference_times"]) > 1
        else 0
        for m in models
    ]
    bars = ax.bar(models, avg_times, yerr=std_times, capsize=5,
                   color=colors[: len(models)])
    ax.set_ylabel("Inference time (ms)")
    ax.set_title("Average Inference Time")
    tops = [h + e for h, e in zip(avg_times, std_times)]
    label_pad = (max(tops) * 0.06) if tops else 1.0
    ax.set_ylim(0, (max(tops) * 1.2) if tops else 1)
    for bar, val, err in zip(bars, avg_times, std_times):
        top = bar.get_height() + err
        ax.text(bar.get_x() + bar.get_width() / 2, top + label_pad,
                 f"{val:.0f}", ha="center", va="bottom", fontsize=9)

    # --- 2. Grouped bar chart: accuracy metrics ---
    ax = axes[1]
    x = range(len(models))
    width = 0.25
    overall = [data[m]["accuracy_overall"] * 100 for m in models]
    when_detected = [data[m]["accuracy_when_detected"] * 100 for m in models]
    det_rate = [data[m]["detection_rate"] * 100 for m in models]

    ax.bar([i - width for i in x], overall, width, label="Accuracy (overall)")
    ax.bar(list(x), when_detected, width, label="Accuracy (when detected)")
    ax.bar([i + width for i in x], det_rate, width, label="Detection rate")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models)
    ax.set_ylabel("Percent")
    ax.set_ylim(0, 105)
    ax.set_title("Accuracy & Detection Rate")
    ax.legend(fontsize=8)

    # --- 3. Bar chart: average confidence ---
    ax = axes[2]
    avg_conf = [
        statistics.mean(data[m]["confidences"]) if data[m]["confidences"] else 0
        for m in models
    ]
    bars = ax.bar(models, avg_conf, color=colors[: len(models)])
    ax.set_ylabel("Confidence")
    ax.set_ylim(0, 1.15)
    ax.set_title("Average Confidence (on detections)")
    for bar, val in zip(bars, avg_conf):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.04,
                 f"{val:.2f}", ha="center", va="bottom", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_path, dpi=150)
    print(f"Saved chart to {out_path}")
    plt.show()


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("predictions.csv")
    out_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if not csv_path.exists():
        print(f"Could not find CSV at: {csv_path}")
        print("Usage: python plot_model_comparison.py /path/to/predictions.csv [output.png]")
        sys.exit(1)

    rows = load_rows(csv_path)
    if not rows:
        print("CSV has no data rows.")
        sys.exit(1)

    models = discover_model_names(rows[0].keys())
    if not models:
        print("Could not find any '<model>_predicted' columns in the CSV.")
        sys.exit(1)

    out_path = Path(out_arg) if out_arg else csv_path.with_name(csv_path.stem + "_comparison.png")
    try:
        make_charts(rows, models, out_path)
    except OSError:
        fallback_path = Path.cwd() / (csv_path.stem + "_comparison.png")
        print(f"Could not save to {out_path}, trying {fallback_path} instead")
        make_charts(rows, models, fallback_path)


if __name__ == "__main__":
    main()