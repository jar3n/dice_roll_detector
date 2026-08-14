"""
    Script to load in the per-run "peaks" CSVs produced by
    noise_data_postprocessing.py and build a grouped bar chart comparing
    noise-floor peak amplitudes against dice-roll peak amplitudes, at each
    filtering setting (Raw, EMA alpha=0.05/0.1/0.2/0.3).

    Also draws a horizontal threshold line suggesting where a dice-roll
    detector could separate "noise" from "real roll" events.

    @author James Englander

    Script written with the help of Claude

    steps:
    1. Import each source's *_peaks.csv
    2. Tag each with a category (Noise / Dice Roll) and a source label
    3. Combine into one long-format dataframe
    4. Plot grouped bars per filtering setting, log-scale y-axis
    5. Compute + draw a horizontal detection threshold line
"""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.core.frame import DataFrame

# ---------------------------------------------------------------------------
# Config: which files belong to which category, and what to call them
# ---------------------------------------------------------------------------

DATA_DIR = Path("~/Documents/665.681_Application_of_Sensor_Systems/course_project/data/experiments/vibe_noise_floor/").expanduser()

def find_file(filename: str, search_root: Path) -> Path:
    """Recursively search for a file by name under search_root."""
    matches = list(search_root.rglob(filename))

    if not matches:
        raise FileNotFoundError(f"Could not find '{filename}' under {search_root}")
    if len(matches) > 1:
        raise ValueError(f"Found multiple matches for '{filename}': {matches}")

    return matches[0]

# (filename, display label, category)
SOURCES: list[tuple[str, str, str]] = [
    ("control_noise_floor_data_peaks.csv", "Control", "Noise"),
    ("repeated_poking_noise_data_peaks.csv", "Poking", "Noise"),
    ("repeated_bumps_on_table_data_peaks.csv", "Bumps on Table", "Noise"),
    ("repeated_dice_roll_data_peaks.csv", "Dice Roll (Trial 1)", "Dice Roll"),
    ("repeated_dice_roll_data_take_2_peaks.csv", "Dice Roll (Trial 2)", "Dice Roll"),
]

# Order the filter settings should appear on the x-axis
FILTER_ORDER: list[str] = [
    "Raw",
    "Filtered EMA alpha=0.05",
    "Filtered EMA alpha=0.1",
    "Filtered EMA alpha=0.2",
    "Filtered EMA alpha=0.3",
]

# Distinct colors per source, grouped by category (blues = noise, oranges/reds = dice)
COLORS: dict[str, str] = {
    "Control": "#4C72B0",
    "Poking": "#7FA6D6",
    "Bumps on Table": "#2E4E7A",
    "Dice Roll (Trial 1)": "#D9622B",
    "Dice Roll (Trial 2)": "#F2A65A",
}


def load_all_sources() -> DataFrame:
    """Load each peaks csv, tag it with source/category, and combine."""

    frames: list[DataFrame] = []

    for filename, label, category in SOURCES:
        filepath: Path = find_file(filename, DATA_DIR)
        df: DataFrame = pd.read_csv(filepath)

        # some csvs have a stray leading space in this column, e.g.
        # " Filtered EMA alpha=0.1" - normalize it
        df["Filtering Applied"] = df["Filtering Applied"].str.strip()

        df["Source"] = label
        df["Category"] = category

        frames.append(df)

    combined: DataFrame = pd.concat(frames, ignore_index=True)
    return combined


def compute_threshold_range(df: DataFrame, filter_name: str) -> tuple[float, float]:
    """
    Range of valid thresholds, computed per filter setting: any value
    between the top of the noise error bars and the bottom of the
    dice-roll error bars will separate the two categories, accounting for
    the spread (std) of each reading rather than just the raw averages.

    Returns (low, high) = (highest noise mean+std, lowest dice mean-std).

    Adjust this function if a different rule is preferred, e.g.:
        - use raw peak averages instead of mean +/- std (wider, looser range)
        - noise_mean + N * noise_std for a different confidence margin
        - a fixed ADC value from datasheet / hardware limits as the high bound
    """

    filtered_df: DataFrame = df[df["Filtering Applied"] == filter_name]

    noise_df: DataFrame = filtered_df[filtered_df["Category"] == "Noise"]
    dice_df: DataFrame = filtered_df[filtered_df["Category"] == "Dice Roll"]

    noise_upper: Any = (
        noise_df["Average Peak Amplitude"]
        + noise_df["Standard Deviation from Average Peak Amplitude"]
    )
    dice_lower: Any = (
        dice_df["Average Peak Amplitude"]
        - dice_df["Standard Deviation from Average Peak Amplitude"]
    )

    low: float = float(noise_upper.max())
    high: float = float(dice_lower.min())

    return low, high


def compute_threshold_midpoint(low: float, high: float) -> float | None:
    """Suggested single threshold value: geometric mean of the range bounds.
    Geometric (not arithmetic) mean is used since the range spans a log scale.
    Returns None if the range is invalid (low >= high), meaning the noise and
    dice-roll error bars overlap and no single threshold cleanly separates them."""
    if low <= 0 or high <= 0 or low >= high:
        return None
    return float(np.sqrt(low * high))


def plot_one_filter(ax: plt.Axes, df: DataFrame, filter_name: str) -> None:
    """Plot a single filter setting's bars + threshold line onto the given axes."""

    sources: list[str] = [label for _, label, _ in SOURCES]

    filtered_df: DataFrame = df[df["Filtering Applied"] == filter_name].set_index("Source")
    filtered_df = filtered_df.reindex(sources)  # enforce consistent bar order

    means: Any = filtered_df["Average Peak Amplitude"].to_numpy()
    stds: Any = filtered_df["Standard Deviation from Average Peak Amplitude"].to_numpy()

    x = np.arange(len(sources))
    bar_colors = [COLORS[source] for source in sources]

    ax.bar(x, means, yerr=stds, capsize=4, color=bar_colors)

    low, high = compute_threshold_range(df, filter_name)
    midpoint: float | None = compute_threshold_midpoint(low, high)

    if midpoint is None:
        # noise and dice-roll error bars overlap - no clean separating value
        ax.text(
            0.5,
            0.95,
            f"No valid threshold\n(bounds cross: {low:,.0f} vs {high:,.0f})",
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=9,
            color="crimson",
            bbox=dict(boxstyle="round", facecolor="white", edgecolor="crimson", alpha=0.9),
        )
    else:
        ax.axhspan(
            low,
            high,
            color="crimson",
            alpha=0.15,
            label=f"Threshold range ({low:,.0f}\u2013{high:,.0f})",
        )
        ax.axhline(
            y=midpoint,
            color="crimson",
            linestyle="--",
            linewidth=2,
            label=f"Suggested threshold ({midpoint:,.0f})",
        )

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(sources, rotation=30, ha="right", fontsize=8)
    ax.set_title(filter_name, fontsize=11)
    ax.set_ylabel("Avg Peak Amplitude (log)")
    ax.grid(axis="y", which="both", linestyle=":", alpha=0.4)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left", fontsize=8)


def plot_all_filters(df: DataFrame, export_path: Path) -> None:
    """Build a grid with one subplot per filtering setting."""

    n_filters: int = len(FILTER_ORDER)
    n_cols = 3
    n_rows = int(np.ceil(n_filters / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))
    axes_flat = axes.flatten()

    for i, filter_name in enumerate(FILTER_ORDER):
        plot_one_filter(axes_flat[i], df, filter_name)

    # hide any unused subplot slots (e.g. 5 filters in a 2x3 grid)
    for j in range(n_filters, len(axes_flat)):
        axes_flat[j].axis("off")

    fig.suptitle("Peak Amplitude: Noise Sources vs. Dice Roll, per Filter Setting", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(export_path, dpi=150)
    print(f"Saved chart to: {export_path}")


if __name__ == "__main__":
    combined_df: DataFrame = load_all_sources()

    for filter_name in FILTER_ORDER:
        low, high = compute_threshold_range(combined_df, filter_name)
        midpoint: float | None = compute_threshold_midpoint(low, high)
        if midpoint is None:
            print(f"{filter_name}: NO VALID THRESHOLD (bounds cross: {low:,.2f} vs {high:,.2f})")
        else:
            print(f"{filter_name}: threshold range = {low:,.2f} - {high:,.2f}  (suggested: {midpoint:,.2f})")

    output_path: Path = DATA_DIR.joinpath("noise_vs_dice_peak_comparison.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_all_filters(combined_df, output_path)