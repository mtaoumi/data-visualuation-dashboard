"""
data_loader.py
==============
Data acquisition and cleaning layer for the dashboard.

Design choices
--------------
* The dataset is synthetic monthly sales/customer data generated deterministically
  with a fixed random seed. This guarantees that anyone cloning the repository
  sees the exact same charts the README screenshots reference, while still
  producing data with realistic structure (seasonality, weekly cycles, category
  variation, outliers).
* Generation is separated from the Streamlit app so the cleaning pipeline can be
  tested or swapped (e.g. for a real CSV) without touching UI code.
* `@st.cache_data` is applied at the call site in `app.py` rather than here, so
  this module stays framework-agnostic and unit-testable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

import numpy as np
import pandas as pd

# A deterministic seed keeps the README screenshots reproducible.
RANDOM_SEED = 42

# Categories chosen to give the grouped bar chart enough visual variety
# without overcrowding the legend.
CATEGORIES: tuple[str, ...] = (
    "Apparel",
    "Electronics",
    "Home Goods",
    "Beauty",
    "Sports",
)

REGIONS: tuple[str, ...] = ("North", "South", "East", "West")


def _seasonal_multiplier(dates: pd.DatetimeIndex) -> np.ndarray:
    """
    Return a multiplicative seasonality factor for each date.

    Two overlapping cycles are used:
    * Annual cycle peaking in mid-year (June/July), trough around December.
    * Weekly cycle peaking on Saturdays.

    Combining them produces a more interesting time series than a pure
    sinusoid, which is important for the line chart to feel like real data.
    """
    day_of_year = dates.dayofyear.to_numpy()
    annual = 1.0 + 0.35 * np.sin(2 * np.pi * (day_of_year - 80) / 365.25)

    day_of_week = dates.dayofweek.to_numpy()
    weekly = 1.0 + 0.15 * np.sin(2 * np.pi * (day_of_week - 5) / 7)

    return annual * weekly


def generate_dataset(
    start: str = "2023-01-01",
    end: str = "2024-12-31",
    categories: Iterable[str] = CATEGORIES,
    regions: Iterable[str] = REGIONS,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """
    Build a tidy, long-format sales dataset.

    Returns
    -------
    DataFrame with columns:
        date       (datetime64) — daily timestamp
        category   (string)     — product category
        region     (string)     — sales region
        revenue    (float)      — daily revenue in USD
        units_sold (int)        — daily unit count
        customers  (int)        — distinct customers that day
        avg_order  (float)      — revenue / units_sold (derived)
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, end=end, freq="D")

    rows = []
    seasonality = _seasonal_multiplier(dates)

    # Per-category baselines give the grouped bar chart meaningful spread.
    category_baselines = {
        "Apparel": 1800,
        "Electronics": 3200,
        "Home Goods": 1400,
        "Beauty": 1100,
        "Sports": 950,
    }

    for cat in categories:
        for region in regions:
            base = category_baselines.get(cat, 1500)
            # Each region gets its own multiplier so heatmap correlations
            # don't collapse to perfect 1.0s.
            region_factor = rng.uniform(0.75, 1.25)

            noise = rng.normal(loc=1.0, scale=0.18, size=len(dates))
            revenue = base * region_factor * seasonality * noise
            revenue = np.clip(revenue, a_min=50, a_max=None)

            # Units roughly track revenue but with their own noise component
            # so the correlation heatmap shows strong-but-not-perfect coupling.
            units = (revenue / rng.uniform(35, 65)) * rng.normal(1.0, 0.1, len(dates))
            units = np.clip(units, a_min=1, a_max=None).astype(int)

            customers = (units * rng.uniform(0.55, 0.85, len(dates))).astype(int)
            customers = np.clip(customers, a_min=1, a_max=None)

            df_chunk = pd.DataFrame(
                {
                    "date": dates,
                    "category": cat,
                    "region": region,
                    "revenue": np.round(revenue, 2),
                    "units_sold": units,
                    "customers": customers,
                }
            )
            rows.append(df_chunk)

    df = pd.concat(rows, ignore_index=True)

    # Derived metric — useful for the metric switcher and a good demonstration
    # of pandas vectorised operations in the project.
    df["avg_order"] = np.round(df["revenue"] / df["units_sold"], 2)

    return df


def load_data() -> pd.DataFrame:
    """
    Public entry point. Returns the cleaned dashboard dataset.

    Kept separate from `generate_dataset` so that swapping the data source
    later (e.g. reading from a CSV or database) only requires changing this
    function — the rest of the application calls `load_data()`.
    """
    df = generate_dataset()

    # Defensive cleaning: drop rows with any NaN, ensure types are correct.
    df = df.dropna()
    df["date"] = pd.to_datetime(df["date"])
    df["category"] = df["category"].astype("category")
    df["region"] = df["region"].astype("category")

    return df.sort_values("date").reset_index(drop=True)


# Friendly labels for metric columns — used by the UI metric switcher.
METRIC_LABELS: dict[str, str] = {
    "revenue": "Revenue (USD)",
    "units_sold": "Units Sold",
    "customers": "Customers",
    "avg_order": "Avg. Order Value",
}


def get_date_bounds(df: pd.DataFrame) -> tuple[datetime, datetime]:
    """Return (min_date, max_date) as Python datetimes — Streamlit needs these."""
    return df["date"].min().to_pydatetime(), df["date"].max().to_pydatetime()
