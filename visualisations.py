"""
visualisations.py
=================
All Matplotlib + Seaborn chart functions for the dashboard.

Design choices
--------------
* Every function accepts a pre-filtered DataFrame. The functions are pure with
  respect to the data — they don't reach into Streamlit state. This keeps them
  unit-testable and reusable.
* A single `apply_theme()` is called at module import time so all charts share
  a consistent look. The palette is a neutral cream/charcoal scheme with a
  single muted accent — the brief specifies a "clean minimal aesthetic".
* Figures use a fixed aspect ratio chosen to look good both in Streamlit's
  default container width and when exported to the README screenshots.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

# Cream/charcoal palette. The accent (a muted terracotta) is used sparingly so
# the dashboard reads as restrained rather than decorative.
PALETTE = {
    "bg": "#F5F1EA",          # cream background
    "surface": "#FBF8F3",     # slightly lighter for chart faces
    "ink": "#2A2A28",         # near-black for text/axes
    "muted": "#7A746B",       # secondary text / gridlines
    "accent": "#B7553A",      # terracotta — used for highlights only
    "accent_soft": "#D9A088", # softer accent for fills
}

# Multi-series palette derived from the same family so charts feel cohesive.
# Picked for ordinal contrast rather than maximum saturation.
SERIES_PALETTE = ["#2A2A28", "#7A746B", "#B7553A", "#9A8A6E", "#5C6B6E"]


def apply_theme() -> None:
    """Configure Matplotlib + Seaborn defaults for the whole module."""
    sns.set_theme(style="white", context="notebook")

    mpl.rcParams.update(
        {
            # Typography — Georgia is widely available and lends an editorial feel
            # that suits a portfolio piece without requiring a font download.
            "font.family": "serif",
            "font.serif": ["Georgia", "DejaVu Serif", "Times New Roman", "serif"],
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "regular",
            "axes.titlepad": 14,
            "axes.labelsize": 10,
            "axes.labelcolor": PALETTE["muted"],
            "axes.edgecolor": PALETTE["muted"],
            "axes.linewidth": 0.8,
            "xtick.color": PALETTE["muted"],
            "ytick.color": PALETTE["muted"],
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            # Generous whitespace, per the brief.
            "figure.facecolor": PALETTE["surface"],
            "axes.facecolor": PALETTE["surface"],
            "savefig.facecolor": PALETTE["surface"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            # Faint gridlines — present for readability, recessive enough not
            # to compete with the data.
            "axes.grid": True,
            "grid.color": PALETTE["muted"],
            "grid.alpha": 0.15,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
            "legend.fontsize": 9,
        }
    )


# Apply once on import so any caller gets the theme for free.
apply_theme()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_fig(figsize: tuple[float, float] = (9, 4.2)) -> tuple[plt.Figure, plt.Axes]:
    """Standardised figure creation so all charts share dimensions."""
    fig, ax = plt.subplots(figsize=figsize, dpi=110)
    return fig, ax


def _format_metric_axis(ax: plt.Axes, metric: str) -> None:
    """Apply currency formatting to revenue/avg_order, plain integers otherwise."""
    if metric in {"revenue", "avg_order"}:
        ax.yaxis.set_major_formatter(
            mpl.ticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )
    else:
        ax.yaxis.set_major_formatter(
            mpl.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
        )


# ---------------------------------------------------------------------------
# Chart 1 — Time series line chart
# ---------------------------------------------------------------------------

def time_series_chart(df: pd.DataFrame, metric: str, metric_label: str) -> plt.Figure:
    """
    Monthly trend of the chosen metric, broken down by category.

    Daily data is resampled to monthly sums (or means for avg_order) so the
    line stays readable across a 2-year window.
    """
    fig, ax = _new_fig(figsize=(9, 4.2))

    agg = "mean" if metric == "avg_order" else "sum"

    # Resample per category. We set `date` as the index, group, resample, then
    # reset back so each row has explicit (date, category, metric) columns.
    monthly = (
        df.set_index("date")
        .groupby("category", observed=True)[metric]
        .resample("MS")
        .agg(agg)
        .reset_index()
    )

    categories = list(monthly["category"].unique())
    for i, cat in enumerate(categories):
        sub = monthly[monthly["category"] == cat]
        ax.plot(
            sub["date"],
            sub[metric],
            label=cat,
            color=SERIES_PALETTE[i % len(SERIES_PALETTE)],
            linewidth=1.6,
            marker="o",
            markersize=3.5,
            markeredgewidth=0,
        )

    ax.set_title(f"{metric_label} over time", loc="left", color=PALETTE["ink"])
    ax.set_xlabel("")
    ax.set_ylabel(metric_label)
    _format_metric_axis(ax, metric)
    ax.legend(loc="upper left", ncol=len(categories), bbox_to_anchor=(0, -0.12))

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Chart 2 — Grouped bar chart
# ---------------------------------------------------------------------------

def grouped_bar_chart(df: pd.DataFrame, metric: str, metric_label: str) -> plt.Figure:
    """
    Category × Region comparison.

    The grouping makes it easy to spot which region drives a given category —
    a question a flat bar chart can't answer.
    """
    fig, ax = _new_fig(figsize=(9, 4.2))

    agg = "mean" if metric == "avg_order" else "sum"
    grouped = (
        df.groupby(["category", "region"], observed=True)[metric]
        .agg(agg)
        .reset_index()
    )

    sns.barplot(
        data=grouped,
        x="category",
        y=metric,
        hue="region",
        ax=ax,
        palette=SERIES_PALETTE[: grouped["region"].nunique()],
        edgecolor="none",
    )

    ax.set_title(
        f"{metric_label} by category and region", loc="left", color=PALETTE["ink"]
    )
    ax.set_xlabel("")
    ax.set_ylabel(metric_label)
    _format_metric_axis(ax, metric)
    ax.legend(title="Region", loc="upper right")

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Chart 3 — Correlation heatmap
# ---------------------------------------------------------------------------

def correlation_heatmap(df: pd.DataFrame) -> plt.Figure:
    """
    Pearson correlations between the numerical metrics.

    Useful sanity check: revenue and units_sold should correlate strongly,
    avg_order should be relatively independent. A diverging colormap centered
    at 0 keeps the visual reading correct for negative correlations too.
    """
    fig, ax = _new_fig(figsize=(6.5, 5))

    numeric = df[["revenue", "units_sold", "customers", "avg_order"]]
    corr = numeric.corr()

    # Custom diverging colormap built from the cream/terracotta palette so the
    # heatmap doesn't break visual continuity with the rest of the dashboard.
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "dashboard_diverging",
        [PALETTE["ink"], PALETTE["bg"], PALETTE["accent"]],
        N=256,
    )

    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap=cmap,
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=0.8,
        linecolor=PALETTE["surface"],
        cbar_kws={"shrink": 0.7, "label": ""},
        annot_kws={"color": PALETTE["ink"], "fontsize": 10},
        ax=ax,
    )

    ax.set_title("Correlation between metrics", loc="left", color=PALETTE["ink"])
    ax.tick_params(axis="x", rotation=0)
    ax.tick_params(axis="y", rotation=0)

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Chart 4 — Distribution plot (violin)
# ---------------------------------------------------------------------------

def distribution_plot(df: pd.DataFrame, metric: str, metric_label: str) -> plt.Figure:
    """
    Distribution of the chosen metric per category, shown as a violin plot.

    Violin > histogram here because we're comparing multiple groups at once;
    overlapping histograms would be hard to read. The inner quartile box gives
    the same summary information a boxplot would.
    """
    fig, ax = _new_fig(figsize=(9, 4.2))

    sns.violinplot(
        data=df,
        x="category",
        y=metric,
        hue="category",
        ax=ax,
        palette=SERIES_PALETTE[: df["category"].nunique()],
        inner="quartile",
        linewidth=0.9,
        cut=0,
        legend=False,
    )

    ax.set_title(
        f"Distribution of {metric_label.lower()} per category",
        loc="left",
        color=PALETTE["ink"],
    )
    ax.set_xlabel("")
    ax.set_ylabel(metric_label)
    _format_metric_axis(ax, metric)

    fig.tight_layout()
    return fig
