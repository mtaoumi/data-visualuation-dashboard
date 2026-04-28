"""
app.py
======
Main Streamlit dashboard.

Run with:
    streamlit run app.py

Design choices
--------------
* Single-file UI layer that delegates data work to `data_loader` and chart
  rendering to `visualisations`. This separation mirrors the model/view split
  of a typical web application and makes the codebase easier to navigate.
* `@st.cache_data` is applied here (not in `data_loader.py`) so the loader
  stays framework-agnostic. The cache is invalidated automatically when the
  source code changes.
* Streamlit's native theming is configured in `.streamlit/config.toml` rather
  than via inline CSS so users can flip light/dark using Streamlit's built-in
  Settings menu (☰ → Settings → Theme).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import data_loader
import visualisations as viz

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Sales & Customer Dashboard",
    page_icon="◐",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "Interactive sales analytics dashboard. "
            "Built with Streamlit, Pandas, Matplotlib and Seaborn. "
            "Portfolio piece — Master's application in computational design."
        ),
    },
)


# ---------------------------------------------------------------------------
# Light, scoped CSS for the bits Streamlit's theme can't control
# ---------------------------------------------------------------------------
# Kept minimal and additive — Streamlit's own theme handles colours so
# light/dark mode keeps working. We only adjust spacing, typography and the
# metric cards.
st.markdown(
    """
    <style>
        /* Tighten the default top padding so the title sits closer to the top */
        .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1300px; }

        /* Editorial serif for headings, matching the chart typography */
        h1, h2, h3, h4 {
            font-family: Georgia, "DejaVu Serif", "Times New Roman", serif !important;
            font-weight: 400 !important;
            letter-spacing: -0.01em;
        }
        h1 { font-size: 2.4rem !important; line-height: 1.15; margin-bottom: 0.2rem; }

        /* Subtle horizontal rule under the title */
        .title-rule {
            height: 1px;
            background: rgba(122, 116, 107, 0.25);
            margin: 1.2rem 0 2rem 0;
        }

        /* Metric cards — generous padding, hairline border */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.35);
            border: 1px solid rgba(122, 116, 107, 0.2);
            border-radius: 4px;
            padding: 1.1rem 1.2rem;
        }
        [data-testid="stMetricLabel"] p {
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: rgba(122, 116, 107, 1);
        }
        [data-testid="stMetricValue"] {
            font-family: Georgia, serif;
            font-size: 1.7rem !important;
        }

        /* Sidebar typography */
        section[data-testid="stSidebar"] h2 {
            font-size: 1.1rem !important;
            margin-top: 0.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cached data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def get_data():
    """Load and cache the dataset for the lifetime of the Streamlit session."""
    return data_loader.load_data()


df = get_data()
min_date, max_date = data_loader.get_date_bounds(df)


# ---------------------------------------------------------------------------
# Sidebar — interactive filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## Filters")
    st.caption("Refine the dataset; charts and metrics update instantly.")

    # Date range — Streamlit's slider works natively with datetime values.
    date_range = st.slider(
        "Date range",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="MMM YYYY",
    )

    # Category multi-select — defaults to all so the dashboard isn't empty.
    all_categories = sorted(df["category"].unique().tolist())
    selected_categories = st.multiselect(
        "Categories",
        options=all_categories,
        default=all_categories,
    )

    # Region multi-select — extra filter, useful for the grouped bar chart.
    all_regions = sorted(df["region"].unique().tolist())
    selected_regions = st.multiselect(
        "Regions",
        options=all_regions,
        default=all_regions,
    )

    # Metric switcher — drives the line chart, bar chart and violin plot.
    metric_keys = list(data_loader.METRIC_LABELS.keys())
    selected_metric = st.selectbox(
        "Primary metric",
        options=metric_keys,
        format_func=lambda k: data_loader.METRIC_LABELS[k],
        index=0,
    )
    metric_label = data_loader.METRIC_LABELS[selected_metric]

    st.markdown("---")
    st.caption(
        "Theme: switch light/dark via the Streamlit menu "
        "(top-right ☰ → Settings → Theme)."
    )


# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

mask = (
    (df["date"] >= pd.Timestamp(date_range[0]))
    & (df["date"] <= pd.Timestamp(date_range[1]))
    & (df["category"].isin(selected_categories))
    & (df["region"].isin(selected_regions))
)

filtered = df[mask].copy()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("# Sales & Customer Dashboard")
st.markdown(
    "<span style='color: rgba(122,116,107,1);'>"
    "Two years of synthetic sales activity across five product categories "
    "and four regions. Use the sidebar to filter."
    "</span>",
    unsafe_allow_html=True,
)
st.markdown("<div class='title-rule'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Summary metric cards
# ---------------------------------------------------------------------------

if filtered.empty:
    st.warning("No data matches the current filters. Widen the selection in the sidebar.")
    st.stop()

# Cards always show revenue/customers/orders headlines plus the chosen metric.
total_revenue = filtered["revenue"].sum()
total_units = int(filtered["units_sold"].sum())
total_customers = int(filtered["customers"].sum())
avg_revenue_per_day = filtered.groupby("date")["revenue"].sum().mean()
peak_day = filtered.groupby("date")["revenue"].sum().idxmax()
peak_value = filtered.groupby("date")["revenue"].sum().max()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total revenue", f"${total_revenue:,.0f}")
col2.metric("Avg. daily revenue", f"${avg_revenue_per_day:,.0f}")
col3.metric("Peak day", f"${peak_value:,.0f}", peak_day.strftime("%b %d, %Y"))
col4.metric("Total units sold", f"{total_units:,}")

st.markdown("&nbsp;")  # vertical breathing room


# ---------------------------------------------------------------------------
# Charts — laid out in a 2×2 grid
# ---------------------------------------------------------------------------

row1_left, row1_right = st.columns(2, gap="large")

with row1_left:
    fig = viz.time_series_chart(filtered, selected_metric, metric_label)
    st.pyplot(fig, use_container_width=True)

with row1_right:
    fig = viz.grouped_bar_chart(filtered, selected_metric, metric_label)
    st.pyplot(fig, use_container_width=True)

row2_left, row2_right = st.columns(2, gap="large")

with row2_left:
    fig = viz.distribution_plot(filtered, selected_metric, metric_label)
    st.pyplot(fig, use_container_width=True)

with row2_right:
    fig = viz.correlation_heatmap(filtered)
    st.pyplot(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Footer — raw data inspection
# ---------------------------------------------------------------------------

with st.expander("Inspect filtered data"):
    st.caption(f"{len(filtered):,} rows match the current filters.")
    st.dataframe(
        filtered.sort_values("date", ascending=False).head(500),
        use_container_width=True,
        hide_index=True,
    )
