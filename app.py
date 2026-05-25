"""
SmartMoney — Capital Rotation by Industry
Streamlit Dashboard

Ranks industries within each sector ETF by capital rotation intensity.
Click an industry to drill down into individual stocks.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from smartmoney.taxonomy import TAXONOMY, SECTOR_ETFS
from smartmoney.data import fetch_ohlcv_batch, compute_weekly_ohlcv
from smartmoney.rotation import (
    calc_industry_rotation,
    rank_industries,
    get_stock_detail,
    calc_rotation_anomalies,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SmartMoney — Capital Rotation",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp { background-color: #0f1117; }
    .block-container { padding-top: 2rem; max-width: 1400px; }

    /* Header */
    .main-title {
        font-size: 28px;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 0;
    }
    .subtitle {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 20px;
    }

    /* Anomaly cards */
    .anomaly-card {
        padding: 10px 14px;
        background: #232738;
        border-radius: 6px;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .anomaly-card.inflow { border-left: 3px solid #34d399; }
    .anomaly-card.outflow { border-left: 3px solid #f87171; }

    /* Table styling */
    .dataframe { font-size: 13px !important; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Stock table header */
    .stock-header {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Fetching market data...")
def load_all_data():
    """Fetch and compute rotation for all sectors."""
    # Collect all tickers
    all_tickers = set()
    for industries in TAXONOMY.values():
        for tickers in industries.values():
            all_tickers.update(tickers)

    # Fetch daily OHLCV
    daily_data = fetch_ohlcv_batch(
        list(all_tickers),
        lookback_days=140,  # ~20 weeks
        cache_dir=".cache",
    )

    # Weekly resample
    weekly_data = compute_weekly_ohlcv(daily_data)

    # Compute per-sector
    sector_results = {}
    all_industry_rotations = {}

    for etf, industries in TAXONOMY.items():
        sector_name = SECTOR_ETFS.get(etf, etf)

        industry_rotations = calc_industry_rotation(weekly_data, industries, window=1)
        industry_rotations_daily = calc_industry_rotation(daily_data, industries, window=5)
        ranking = rank_industries(industry_rotations_daily, etf)

        stock_details = {}
        for ind_name, tickers in industries.items():
            clean_name = ind_name.lstrip("*")
            sd = get_stock_detail(daily_data, tickers, window=5)
            if not sd.empty:
                stock_details[clean_name] = sd

        sector_results[etf] = {
            "name": sector_name,
            "ranking": ranking,
            "time_series": industry_rotations,
            "stock_detail": stock_details,
        }

        for k, v in industry_rotations.items():
            all_industry_rotations[k] = v

    # Anomalies
    anomalies = calc_rotation_anomalies(all_industry_rotations)

    return sector_results, anomalies, len(daily_data)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
def build_ranking_chart(ranking: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of industry rotation ranking."""
    if ranking.empty:
        return go.Figure()

    sorted_df = ranking.sort_values("rotation_rel", ascending=True)

    colors = [
        "#34d399" if v >= 0.5 else "#f87171"
        for v in sorted_df["rotation_rel"]
    ]

    labels = [
        f"{len(sorted_df) - i}. {row['industry']}"
        for i, (_, row) in enumerate(sorted_df.iterrows())
    ]

    fig = go.Figure(go.Bar(
        y=labels,
        x=sorted_df["rotation_rel"],
        orientation="h",
        marker_color=colors,
        hovertemplate="%{y}<br>Rotation: %{x:.4f}<extra></extra>",
    ))

    fig.update_layout(
        height=max(400, len(sorted_df) * 28),
        margin=dict(l=250, r=20, t=10, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=11),
        xaxis=dict(
            gridcolor="#2d3148",
            zeroline=True,
            zerolinecolor="#4a5568",
            range=[0, max(0.7, sorted_df["rotation_rel"].max() + 0.05)],
        ),
        yaxis=dict(automargin=True),
        bargap=0.3,
    )

    return fig


def build_timeseries_chart(ts_df: pd.DataFrame, industry_name: str) -> go.Figure:
    """Bar chart of rotation over time for an industry."""
    if ts_df.empty:
        return go.Figure()

    colors = [
        "#34d399" if v >= 0.5 else "#f87171"
        for v in ts_df["rotation_rel"]
    ]

    fig = go.Figure(go.Bar(
        x=ts_df["date"],
        y=ts_df["rotation_rel"],
        marker_color=colors,
        hovertemplate="%{x}<br>Rotation: %{y:.4f}<extra></extra>",
    ))

    fig.update_layout(
        height=280,
        margin=dict(l=50, r=20, t=10, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=11),
        xaxis=dict(gridcolor="#2d3148", tickangle=-45),
        yaxis=dict(
            title="Capital Rotation Rel",
            gridcolor="#2d3148",
            range=[0, 0.7],
        ),
        bargap=0.15,
    )

    return fig


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
def main():
    # Header
    st.markdown('<div class="main-title">SmartMoney — Capital Rotation by Industry</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="subtitle">Latest week: {datetime.now().strftime("%Y-%m-%d")} · '
        f'20w lookback · 5d rotation window</div>',
        unsafe_allow_html=True,
    )

    # Load data
    sector_results, anomalies, n_tickers = load_all_data()

    # Sector selector
    etf_options = list(TAXONOMY.keys())
    etf_labels = {etf: f"{etf} - {SECTOR_ETFS.get(etf, etf)}" for etf in etf_options}

    selected_etf = st.selectbox(
        "Select ETF (Sector)",
        etf_options,
        format_func=lambda x: etf_labels[x],
        index=0,
    )

    sector = sector_results[selected_etf]
    ranking = sector["ranking"]

    # Main layout: ranking chart | detail panel
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        fig = build_ranking_chart(ranking)
        # Use plotly_chart with selection
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            key="ranking",
            on_select="rerun",
        )

    # Determine selected industry
    selected_industry = None

    # Check if user clicked a bar
    if event and event.selection and event.selection.points:
        point = event.selection.points[0]
        # Extract industry name from label (remove rank prefix)
        label = point.get("y", "")
        if isinstance(label, str) and ". " in label:
            selected_industry = label.split(". ", 1)[1]

    # Default to top industry if nothing selected
    if selected_industry is None and not ranking.empty:
        selected_industry = ranking.iloc[0]["industry"]

    with col_right:
        if selected_industry:
            st.markdown(f"### {selected_industry}")

            # Time series
            ts = sector["time_series"].get(selected_industry)
            if ts is not None and not ts.empty:
                ts_fig = build_timeseries_chart(ts, selected_industry)
                st.plotly_chart(ts_fig, use_container_width=True)

            # Industry info
            ind_info = ranking[ranking["industry"] == selected_industry]
            if not ind_info.empty:
                intra = ind_info.iloc[0]["rotation_rel"]
                st.markdown(
                    f'<div class="stock-header">Stocks (latest week) | Intra.: {intra:.3f}</div>',
                    unsafe_allow_html=True,
                )

            # Stock table
            stocks = sector["stock_detail"].get(selected_industry)
            if stocks is not None and not stocks.empty:
                # Search filter
                search = st.text_input(
                    "Search ticker",
                    placeholder="Search ticker...",
                    label_visibility="collapsed",
                )

                display_df = stocks.copy()
                if search:
                    display_df = display_df[
                        display_df["ticker"].str.contains(search.upper())
                    ]

                # Format for display
                display_df = display_df.rename(columns={
                    "ticker": "Ticker",
                    "rotation": "Capital Rotation Rel",
                    "trend": "Capital Trend Self",
                    "last_close": "Last Week Close",
                    "weekly_change_pct": "Weekly Change %",
                })

                # Style the dataframe
                def color_change(val):
                    if isinstance(val, (int, float)):
                        color = "#34d399" if val >= 0 else "#f87171"
                        return f"color: {color}"
                    return ""

                styled = display_df.style.applymap(
                    color_change, subset=["Weekly Change %"]
                ).format({
                    "Capital Rotation Rel": "{:.2f}",
                    "Capital Trend Self": "{:.2f}",
                    "Last Week Close": "{:.2f}",
                    "Weekly Change %": "{:+.2f}%",
                })

                st.dataframe(
                    styled,
                    use_container_width=True,
                    hide_index=True,
                    height=min(400, 35 * len(display_df) + 38),
                )

    # Anomalies section
    if not anomalies.empty:
        st.markdown("---")
        st.markdown("### Rotation Anomalies")
        st.caption("Industries with statistically unusual rotation changes")

        inflows = anomalies[anomalies["direction"] == "inflow_surge"]
        outflows = anomalies[anomalies["direction"] == "outflow_surge"]

        a_left, a_right = st.columns(2)

        with a_left:
            if not inflows.empty:
                st.markdown("**:green[Unusual Inflow]**")
                for _, row in inflows.iterrows():
                    st.markdown(
                        f'<div class="anomaly-card inflow">'
                        f'<span>{row["industry"]}</span>'
                        f'<span style="color:#34d399;font-weight:600">Z: {row["zscore"]:.2f}</span>'
                        f'<span style="color:#94a3b8;font-size:12px">Rotation: {row["rotation_rel"]:.1%}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        with a_right:
            if not outflows.empty:
                st.markdown("**:red[Unusual Outflow]**")
                for _, row in outflows.iterrows():
                    st.markdown(
                        f'<div class="anomaly-card outflow">'
                        f'<span>{row["industry"]}</span>'
                        f'<span style="color:#f87171;font-weight:600">Z: {row["zscore"]:.2f}</span>'
                        f'<span style="color:#94a3b8;font-size:12px">Rotation: {row["rotation_rel"]:.1%}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # Footer
    st.markdown("---")
    st.caption(
        f"SmartMoney v0.1 · {n_tickers} tickers · "
        f"Part of the [Investment Insights Toolkit](https://github.com/hong-chu) · "
        f"Data updates every ~4 hours"
    )


if __name__ == "__main__":
    main()
