"""
SmartMoney — Capital Rotation by Industry
Single-page Streamlit dashboard with top tabs.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from smartmoney.taxonomy import TAXONOMY, SECTOR_ETFS
from smartmoney.loader import load_all_data

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
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    .block-container { padding-top: 2rem; max-width: 1400px; }
    .main-title {
        font-size: 28px; font-weight: 700; color: #e2e8f0; margin-bottom: 0;
    }
    .subtitle {
        font-size: 14px; color: #94a3b8; margin-bottom: 20px;
    }
    .anomaly-card {
        padding: 10px 14px; background: #232738; border-radius: 6px;
        margin-bottom: 6px; display: flex; justify-content: space-between;
        align-items: center;
    }
    .anomaly-card.inflow  { border-left: 3px solid #34d399; }
    .anomaly-card.outflow { border-left: 3px solid #f87171; }
    .stock-header { font-size: 14px; color: #94a3b8; margin-bottom: 8px; }
    .dataframe { font-size: 13px !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stSidebar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CUMULATIVE_COLOR = "#6b7280"

# AI Themes layer metadata
AI_LAYERS = {
    "AI_EDGE": {"name": "AI Edge & Physical AI", "icon": "👁️", "color": "#ec4899"},    # pink
    "AI_MEMORY": {"name": "AI Memory & Storage", "icon": "💾", "color": "#06b6d4"},    # cyan
    "AI_NETWORK": {"name": "AI Networking & Optical", "icon": "🔗", "color": "#8b5cf6"},  # violet
    "AI_COMPUTE": {"name": "AI Compute & Cloud", "icon": "🧠", "color": "#f97316"},   # orange
    "AI_SEMI": {"name": "AI Semi Infrastructure", "icon": "⚙️", "color": "#22c55e"},   # green
    "AI_POWER": {"name": "AI Power & Energy", "icon": "⚡", "color": "#eab308"},       # yellow
    "AI_SOFTWARE": {"name": "AI Software & Apps", "icon": "💻", "color": "#f43f5e"},   # rose/red
    "AI_ADJACENT": {"name": "AI Adjacent", "icon": "🛰️", "color": "#94a3b8"},         # grey
}
AI_LAYER_KEYS = list(AI_LAYERS.keys())

# Physical AI layer metadata
PAI_LAYERS = {
    "PAI_ROBOTS": {"name": "Robots by Application", "icon": "🤖", "color": "#f97316"},   # orange
    "PAI_AV": {"name": "Autonomous Vehicles", "icon": "🚗", "color": "#06b6d4"},          # cyan
    "PAI_AERIAL": {"name": "Aerial / Drones", "icon": "🛩️", "color": "#8b5cf6"},          # violet
    "PAI_INDUSTRY": {"name": "Autonomy by Industry", "icon": "🏭", "color": "#22c55e"},    # green
    "PAI_SENSING": {"name": "Perception / Sensing", "icon": "👁️", "color": "#ec4899"},     # pink
    "PAI_MOTION": {"name": "Motion & Navigation", "icon": "⚙️", "color": "#eab308"},       # yellow
    "PAI_SIM": {"name": "Simulation / Software", "icon": "🎮", "color": "#3b82f6"},        # blue
    "PAI_WEARABLE": {"name": "Wearables / AR / XR", "icon": "🥽", "color": "#f43f5e"},     # rose
}

# Quadrant colors (matching quant-net-flow style)
Q_ACCUMULATION   = "#34d399"  # green  — top-right: buying + accelerating
Q_SELLING_DRIES  = "#a78bfa"  # purple — top-left:  selling + accelerating (selling dries up)
Q_DISTRIBUTION   = "#f87171"  # red    — bottom-left: selling + decelerating
Q_PROFIT_TAKING  = "#fbbf24"  # gold   — bottom-right: buying + decelerating (profit-taking)


def _quadrant_color(rotation: float, zscore: float) -> str:
    """Assign color based on which quadrant the point falls in."""
    if rotation >= 0 and zscore >= 0:
        return Q_ACCUMULATION
    elif rotation < 0 and zscore >= 0:
        return Q_SELLING_DRIES
    elif rotation < 0 and zscore < 0:
        return Q_DISTRIBUTION
    else:
        return Q_PROFIT_TAKING


def _quadrant_label(rotation: float, zscore: float) -> str:
    if rotation >= 0 and zscore >= 0:
        return "Accumulation"
    elif rotation < 0 and zscore >= 0:
        return "Selling Dries Up"
    elif rotation < 0 and zscore < 0:
        return "Distribution"
    else:
        return "Profit-Taking"


# ═══════════════════════════════════════════════════════════════════════════
# Chart builders — Overview tab
# ═══════════════════════════════════════════════════════════════════════════
def build_sector_bar(sector_ts: pd.DataFrame, sector_name: str) -> go.Figure:
    """Small weekly rotation bar chart for one sector."""
    if sector_ts.empty:
        return go.Figure()

    colors = ["#34d399" if v >= 0 else "#f87171" for v in sector_ts["rotation_rel"]]
    cumulative = sector_ts["rotation_rel"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sector_ts["date"], y=sector_ts["rotation_rel"],
        marker_color=colors, name="Weekly",
        hovertemplate="%{x}<br>Rotation: %{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=sector_ts["date"], y=cumulative,
        mode="lines", line=dict(color=CUMULATIVE_COLOR, width=1.5),
        name="Cumulative", yaxis="y2",
        hovertemplate="%{x}<br>Cumulative: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=sector_name, font=dict(size=13, color="#e2e8f0"), x=0.5),
        height=220,
        margin=dict(l=40, r=40, t=35, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=10), showlegend=False,
        xaxis=dict(gridcolor="#2d3148", tickangle=-45, tickfont=dict(size=9)),
        yaxis=dict(gridcolor="#2d3148", zeroline=True,
                   zerolinecolor="#94a3b8", zerolinewidth=1, range=[-1, 1]),
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    zeroline=False, tickfont=dict(size=9, color=CUMULATIVE_COLOR)),
        bargap=0.15,
    )
    return fig


def build_sector_latest_bar(sector_results: dict) -> go.Figure:
    """Horizontal bar ranking all sectors by latest rotation."""
    rows = []
    for etf, data in sector_results.items():
        ts = data["sector_ts_weekly"]
        if ts is not None and not ts.empty:
            rows.append({"sector": f"{etf} - {data['name']}",
                         "rotation_rel": ts["rotation_rel"].iloc[-1]})
    if not rows:
        return go.Figure()

    df = pd.DataFrame(rows).sort_values("rotation_rel", ascending=True)
    colors = ["#34d399" if v >= 0 else "#f87171" for v in df["rotation_rel"]]
    max_abs = max(abs(df["rotation_rel"].min()), abs(df["rotation_rel"].max()), 0.3) + 0.05

    fig = go.Figure(go.Bar(
        y=df["sector"], x=df["rotation_rel"], orientation="h",
        marker_color=colors,
        hovertemplate="%{y}<br>Rotation: %{x:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Sector Rotation Ranking (Latest Week)",
                   font=dict(size=15, color="#e2e8f0")),
        height=max(350, len(df) * 35),
        margin=dict(l=220, r=20, t=40, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=11),
        xaxis=dict(gridcolor="#2d3148", zeroline=True,
                   zerolinecolor="#94a3b8", zerolinewidth=1.5,
                   range=[-max_abs, max_abs],
                   title="← Selling | Buying →",
                   title_font=dict(size=11, color="#94a3b8")),
        yaxis=dict(automargin=True), bargap=0.3,
    )
    return fig


def build_anomaly_scatter(all_zscores: pd.DataFrame, anomalies: pd.DataFrame) -> go.Figure:
    """
    Scatter: X = Capital Rotation, Y = Z-score.
    Colored by quadrant like quant-net-flow.
    Only anomalies (|Z| > 2) get text labels.
    """
    fig = go.Figure()

    if all_zscores.empty:
        return fig

    # Assign quadrant color and label to each industry
    df = all_zscores.copy()
    df["color"] = df.apply(lambda r: _quadrant_color(r["rotation_rel"], r["zscore"]), axis=1)
    df["quadrant"] = df.apply(lambda r: _quadrant_label(r["rotation_rel"], r["zscore"]), axis=1)

    # Label: top 10 with Z > 2 and bottom 10 with Z < -2
    top10 = set(df[df["zscore"] > 2].nlargest(10, "zscore")["industry"])
    bot10 = set(df[df["zscore"] < -2].nsmallest(10, "zscore")["industry"])
    labeled_set = top10 | bot10
    df["is_labeled"] = df["industry"].isin(labeled_set)

    # One trace per quadrant for clean legend
    quadrant_meta = [
        ("Accumulation",    Q_ACCUMULATION),
        ("Selling Dries Up", Q_SELLING_DRIES),
        ("Distribution",    Q_DISTRIBUTION),
        ("Profit-Taking",   Q_PROFIT_TAKING),
    ]

    for q_name, q_color in quadrant_meta:
        # Unlabeled dots
        subset = df[(df["quadrant"] == q_name) & (~df["is_labeled"])]
        if not subset.empty:
            fig.add_trace(go.Scatter(
                x=subset["rotation_rel"], y=subset["zscore"],
                mode="markers",
                marker=dict(size=7, color=q_color, opacity=0.6,
                            line=dict(width=0.5, color="#1a1d29")),
                name=q_name,
                customdata=subset["industry"],
                hovertemplate=(
                    "<b>%{customdata}</b><br>"
                    "Rotation: %{x:.3f}<br>"
                    "Z-Score: %{y:.2f}<extra></extra>"),
                legendgroup=q_name,
            ))

        # Labeled dots — same style + text
        labeled = df[(df["quadrant"] == q_name) & (df["is_labeled"])]
        if not labeled.empty:
            fig.add_trace(go.Scatter(
                x=labeled["rotation_rel"], y=labeled["zscore"],
                mode="markers+text",
                marker=dict(size=7, color=q_color, opacity=0.6,
                            line=dict(width=0.5, color="#1a1d29")),
                text=labeled["industry"],
                textposition="top center",
                textfont=dict(size=9, color="#e2e8f0"),
                customdata=labeled["industry"],
                hovertemplate=(
                    "<b>%{customdata}</b><br>"
                    "Rotation: %{x:.3f}<br>"
                    "Z-Score: %{y:.2f}<extra></extra>"),
                legendgroup=q_name, showlegend=False,
            ))

    # Center lines
    fig.add_vline(x=0, line_color="#4b5563", line_width=1)
    fig.add_hline(y=0, line_color="#4b5563", line_width=1)

    # Z-score threshold lines
    fig.add_hline(y=2, line_dash="dash", line_color="#4b5563", line_width=1)
    fig.add_hline(y=-2, line_dash="dash", line_color="#4b5563", line_width=1)

    # Quadrant corner labels
    annotations = [
        dict(x=0.98, y=0.98, text="ACCUMULATION",
             font=dict(size=11, color=Q_ACCUMULATION, family="sans-serif"),
             showarrow=False, xref="paper", yref="paper",
             xanchor="right", yanchor="top"),
        dict(x=0.02, y=0.98, text="SELLING DRIES UP",
             font=dict(size=11, color=Q_SELLING_DRIES, family="sans-serif"),
             showarrow=False, xref="paper", yref="paper",
             xanchor="left", yanchor="top"),
        dict(x=0.02, y=0.02, text="DISTRIBUTION",
             font=dict(size=11, color=Q_DISTRIBUTION, family="sans-serif"),
             showarrow=False, xref="paper", yref="paper",
             xanchor="left", yanchor="bottom"),
        dict(x=0.98, y=0.02, text="PROFIT-TAKING",
             font=dict(size=11, color=Q_PROFIT_TAKING, family="sans-serif"),
             showarrow=False, xref="paper", yref="paper",
             xanchor="right", yanchor="bottom"),
    ]

    fig.update_layout(
        height=600,
        margin=dict(l=60, r=40, t=40, b=60),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=11),
        annotations=annotations,
        xaxis=dict(
            title="Capital Rotation  ← Selling | Buying →",
            title_font=dict(size=11, color="#94a3b8"),
            gridcolor="#2d3148", zeroline=False,
            range=[-1.1, 1.1],
        ),
        yaxis=dict(
            title="Z-Score  ← Decelerating | Accelerating →",
            title_font=dict(size=11, color="#94a3b8"),
            gridcolor="#2d3148", zeroline=False,
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="center", x=0.5, font=dict(size=10),
            bgcolor="rgba(0,0,0,0)", itemsizing="constant",
        ),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Chart builders — Sector Breakdown tab
# ═══════════════════════════════════════════════════════════════════════════
def build_ranking_chart(ranking: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of industry rotation ranking."""
    if ranking.empty:
        return go.Figure()

    sorted_df = ranking.sort_values("rotation_rel", ascending=True)
    colors = ["#34d399" if v >= 0 else "#f87171" for v in sorted_df["rotation_rel"]]
    labels = [
        f"{len(sorted_df) - i}. {row['industry']}"
        for i, (_, row) in enumerate(sorted_df.iterrows())
    ]

    fig = go.Figure(go.Bar(
        y=labels, x=sorted_df["rotation_rel"], orientation="h",
        marker_color=colors,
        hovertemplate="%{y}<br>Rotation: %{x:.3f}<extra></extra>",
    ))
    max_abs = max(abs(sorted_df["rotation_rel"].min()),
                  abs(sorted_df["rotation_rel"].max()), 0.3) + 0.05

    fig.update_layout(
        height=max(400, len(sorted_df) * 28),
        margin=dict(l=250, r=20, t=10, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=11),
        xaxis=dict(gridcolor="#2d3148", zeroline=True,
                   zerolinecolor="#94a3b8", zerolinewidth=1.5,
                   range=[-max_abs, max_abs],
                   title="← Selling | Buying →",
                   title_font=dict(size=11, color="#94a3b8")),
        yaxis=dict(automargin=True), bargap=0.3,
    )
    return fig


def build_timeseries_chart(ts_df: pd.DataFrame) -> go.Figure:
    """Bar chart of rotation over time + grey cumulative flow line."""
    if ts_df.empty:
        return go.Figure()

    colors = ["#34d399" if v >= 0 else "#f87171" for v in ts_df["rotation_rel"]]
    cumulative = ts_df["rotation_rel"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ts_df["date"], y=ts_df["rotation_rel"],
        marker_color=colors, name="Weekly Rotation",
        hovertemplate="%{x}<br>Rotation: %{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=cumulative,
        mode="lines", line=dict(color=CUMULATIVE_COLOR, width=2),
        name="Cumulative Flow", yaxis="y2",
        hovertemplate="%{x}<br>Cumulative: %{y:.3f}<extra></extra>",
    ))

    fig.update_layout(
        height=380,
        margin=dict(l=50, r=50, t=10, b=50),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=10)),
        xaxis=dict(gridcolor="#2d3148", tickangle=-45),
        yaxis=dict(title="Capital Rotation Rel", gridcolor="#2d3148",
                   zeroline=True, zerolinecolor="#94a3b8", range=[-1, 1]),
        yaxis2=dict(title="Cumulative Flow", overlaying="y", side="right",
                    showgrid=False, zeroline=False,
                    title_font=dict(color=CUMULATIVE_COLOR, size=11),
                    tickfont=dict(color=CUMULATIVE_COLOR)),
        bargap=0.15,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Tab content renderers
# ═══════════════════════════════════════════════════════════════════════════
def render_overview(sector_results, anomalies, all_zscores):
    """Overview tab: sector ranking + weekly grid + anomaly scatter."""

    st.plotly_chart(build_sector_latest_bar(sector_results), use_container_width=True)

    st.markdown("---")
    st.markdown("### Weekly Capital Rotation by Sector")
    st.caption("Green = net buying · Red = net selling · Grey line = cumulative flow")

    etf_list = [k for k in TAXONOMY.keys() if not k.startswith("AI_") and not k.startswith("PAI_")]
    for i in range(0, len(etf_list), 3):
        cols = st.columns(3, gap="medium")
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(etf_list):
                break
            etf = etf_list[idx]
            data = sector_results[etf]
            with col:
                st.plotly_chart(
                    build_sector_bar(data["sector_ts_weekly"],
                                     f"{etf} - {data['name']}"),
                    use_container_width=True,
                )

    # Fund Flow Anomaly Scatter
    st.markdown("---")
    st.markdown("### Fund Flow Anomaly Scatter")
    st.caption("Each dot = one industry · Labeled = top/bottom 10 anomalies (|Z| > 2)")

    st.plotly_chart(build_anomaly_scatter(all_zscores, anomalies),
                    use_container_width=True)

    if not anomalies.empty:
        with st.expander(f"Anomalous Industries ({len(anomalies)})", expanded=False):
            # Build industry → representative tickers lookup
            ind_tickers = {}
            for industries in TAXONOMY.values():
                for ind_name, tickers in industries.items():
                    clean = ind_name.lstrip("*")
                    ind_tickers[clean] = tickers

            display_anom = anomalies[["industry", "rotation_rel", "zscore", "direction"]].copy()
            display_anom.insert(1, "stocks", display_anom["industry"].apply(
                lambda ind: ", ".join(ind_tickers.get(ind, [])[:6])))
            display_anom["rotation_rel"] = display_anom["rotation_rel"].apply(lambda v: f"{v:+.3f}")
            display_anom["zscore"] = display_anom["zscore"].apply(lambda v: f"{v:+.2f}")
            display_anom["direction"] = display_anom["direction"].apply(
                lambda v: "Inflow Surge" if v == "inflow_surge" else "Outflow Surge")
            st.dataframe(
                display_anom.rename(columns={
                    "industry": "Industry", "stocks": "Representative Stocks",
                    "rotation_rel": "Rotation",
                    "zscore": "Z-Score", "direction": "Direction"}),
                use_container_width=True, hide_index=True,
            )


def _format_dollar(val):
    """Format dollar value to human-readable (K, M, B, T)."""
    abs_val = abs(val)
    if abs_val >= 1e12:
        return f"{val/1e12:.1f}T"
    elif abs_val >= 1e9:
        return f"{val/1e9:.1f}B"
    elif abs_val >= 1e6:
        return f"{val/1e6:.1f}M"
    elif abs_val >= 1e3:
        return f"{val/1e3:.0f}K"
    return f"{val:.0f}"


def build_stock_flow_chart(ts_df: pd.DataFrame, ticker: str) -> go.Figure:
    """Small daily fund flow bar chart for one stock with grey cumulative line."""
    if ts_df.empty or "net_flow" not in ts_df.columns:
        return go.Figure()

    colors = ["#34d399" if v >= 0 else "#f87171" for v in ts_df["net_flow"]]
    cumulative = ts_df["net_flow"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ts_df["date"], y=ts_df["net_flow"],
        marker_color=colors,
        hovertemplate="%{x}<br>Net Flow: %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=cumulative,
        mode="lines", line=dict(color=CUMULATIVE_COLOR, width=1.5),
        yaxis="y2",
        hovertemplate="%{x}<br>Cumulative: %{y:,.0f}<extra></extra>",
    ))

    # Auto-scale y-axis symmetrically
    max_abs = ts_df["net_flow"].abs().max()
    if max_abs == 0:
        max_abs = 1

    # Build custom tick values/text for finance-friendly labels (K/M/B)
    def _make_ticks(max_val):
        if max_val >= 1e9:
            step = max(1, round(max_val / 1e9 / 3)) * 1e9
            fmt = lambda v: f"{v/1e9:.0f}B" if v != 0 else "0"
        elif max_val >= 1e6:
            step = max(1, round(max_val / 1e6 / 3)) * 1e6
            fmt = lambda v: f"{v/1e6:.0f}M" if v != 0 else "0"
        elif max_val >= 1e3:
            step = max(1, round(max_val / 1e3 / 3)) * 1e3
            fmt = lambda v: f"{v/1e3:.0f}K" if v != 0 else "0"
        else:
            return None, None
        tvals = []
        v = 0
        while v <= max_val * 1.1:
            tvals.append(v)
            if v != 0:
                tvals.append(-v)
            v += step
        tvals.sort()
        ttext = [fmt(v) if v >= 0 else f"-{fmt(abs(v))}" for v in tvals]
        return tvals, ttext

    y1_tvals, y1_ttext = _make_ticks(max_abs)
    cum_max = cumulative.abs().max()
    y2_tvals, y2_ttext = _make_ticks(cum_max if cum_max > 0 else 1)

    fig.update_layout(
        title=dict(text=ticker, font=dict(size=12, color="#e2e8f0"), x=0.5),
        height=180,
        margin=dict(l=50, r=30, t=30, b=25),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=9), showlegend=False,
        xaxis=dict(gridcolor="#2d3148", tickangle=-45, tickfont=dict(size=8),
                   showticklabels=False),
        yaxis=dict(gridcolor="#2d3148", zeroline=True,
                   zerolinecolor="#94a3b8", zerolinewidth=1,
                   range=[-max_abs * 1.1, max_abs * 1.1],
                   tickvals=y1_tvals, ticktext=y1_ttext),
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    zeroline=False, tickfont=dict(size=8, color=CUMULATIVE_COLOR),
                    tickvals=y2_tvals, ticktext=y2_ttext),
        bargap=0.1,
    )
    return fig


def render_sector_breakdown(sector_results, anomalies, weight_key="equal"):
    """Sector Breakdown tab: industry ranking + drill-down + stock fund flow grid."""

    etf_options = [k for k in TAXONOMY.keys() if not k.startswith("AI_") and not k.startswith("PAI_")]
    etf_labels = {etf: f"{etf} - {SECTOR_ETFS.get(etf, etf)}" for etf in etf_options}

    selected_etf = st.selectbox(
        "Select ETF (Sector)", etf_options,
        format_func=lambda x: etf_labels[x], index=0,
    )

    sector = sector_results[selected_etf]
    ranking = sector["ranking"]

    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        fig = build_ranking_chart(ranking)
        event = st.plotly_chart(
            fig, use_container_width=True, key="ranking", on_select="rerun",
            config={"displayModeBar": False},
        )

    selected_industry = None
    if event and event.selection and event.selection.points:
        point = event.selection.points[0]
        label = point.get("y", "")
        if isinstance(label, str) and ". " in label:
            selected_industry = label.split(". ", 1)[1]

    if selected_industry is None and not ranking.empty:
        selected_industry = ranking.iloc[0]["industry"]

    with col_right:
        if selected_industry:
            st.markdown(f"### {selected_industry}")

            ts = sector["time_series"].get(selected_industry)
            if ts is not None and not ts.empty:
                st.plotly_chart(build_timeseries_chart(ts), use_container_width=True)

            ind_info = ranking[ranking["industry"] == selected_industry]
            if not ind_info.empty:
                intra = ind_info.iloc[0]["rotation_rel"]
                st.markdown(
                    f'<div class="stock-header">'
                    f'Stocks (latest week) | Rotation: {intra:.3f}</div>',
                    unsafe_allow_html=True,
                )

            stocks = sector["stock_detail"].get(selected_industry)
            if stocks is not None and not stocks.empty:
                search = st.text_input(
                    "Search ticker", placeholder="Search ticker...",
                    label_visibility="collapsed",
                )

                # Sort by rotation descending
                display_df = stocks.copy().sort_values("rotation", ascending=False)
                if search:
                    display_df = display_df[
                        display_df["ticker"].str.contains(search.upper())]

                # Compute weight % based on weighting mode
                if weight_key == "market_cap":
                    total_dv = display_df["dollar_volume"].sum()
                    if total_dv > 0:
                        display_df["weight"] = (display_df["dollar_volume"] / total_dv * 100).round(1)
                    else:
                        display_df["weight"] = round(100.0 / len(display_df), 1)
                else:
                    display_df["weight"] = round(100.0 / len(display_df), 1)

                display_df = display_df.rename(columns={
                    "ticker": "Ticker",
                    "weight": "Weight %",
                    "rotation": "Capital Rotation Rel",
                    "trend": "Capital Trend Self",
                    "last_close": "Last Week Close",
                    "weekly_change_pct": "Weekly Change %",
                })

                # Select and order columns
                show_cols = ["Ticker", "Weight %", "Capital Rotation Rel",
                             "Capital Trend Self", "Last Week Close", "Weekly Change %"]
                display_df = display_df[show_cols].copy()

                display_df["Capital Rotation Rel"] = display_df["Capital Rotation Rel"].round(2)
                display_df["Capital Trend Self"] = display_df["Capital Trend Self"].round(2)
                display_df["Last Week Close"] = display_df["Last Week Close"].round(2)
                display_df["Weekly Change %"] = display_df["Weekly Change %"].apply(
                    lambda v: f"{v:+.2f}%")

                st.dataframe(
                    display_df, use_container_width=True, hide_index=True,
                    height=min(400, 35 * len(display_df) + 38),
                    column_config={
                        "Weekly Change %": st.column_config.TextColumn("Weekly Change %"),
                    },
                )

    # Stock fund flow charts grid (daily data)
    if selected_industry:
        stock_ts = sector.get("stock_daily_rotation", {}).get(selected_industry, {})
        if stock_ts:
            st.markdown("---")
            st.markdown(f"### Stock Fund Flow — {selected_industry}")
            st.caption("Daily net fund flow for each stock (5-day rolling window, dollar-weighted)")

            # Sort tickers by latest net_flow descending
            sorted_tickers = []
            for ticker, ts_df in stock_ts.items():
                if not ts_df.empty and "net_flow" in ts_df.columns:
                    latest = ts_df["net_flow"].iloc[-1]
                    sorted_tickers.append((ticker, latest, ts_df))
            sorted_tickers.sort(key=lambda x: x[1], reverse=True)

            # 3-column grid
            for i in range(0, len(sorted_tickers), 3):
                cols = st.columns(3, gap="small")
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(sorted_tickers):
                        break
                    ticker, _, ts_df = sorted_tickers[idx]
                    with col:
                        st.plotly_chart(
                            build_stock_flow_chart(ts_df, ticker),
                            use_container_width=True,
                        )


def _build_ai_combined_ranking(ai_sector_results, layers_config=None):
    """Build a combined ranking of all subcategories across all layers."""
    if layers_config is None:
        layers_config = AI_LAYERS
    rows = []
    for layer_key, layer_meta in layers_config.items():
        if layer_key not in ai_sector_results:
            continue
        sector = ai_sector_results[layer_key]
        ranking = sector.get("ranking")
        if ranking is None or ranking.empty:
            continue
        for _, row in ranking.iterrows():
            rows.append({
                "industry": row["industry"],
                "rotation_rel": row["rotation_rel"],
                "trend": row["trend"],
                "n_stocks": row["n_stocks"],
                "layer_key": layer_key,
                "layer_name": layer_meta["name"],
                "layer_icon": layer_meta["icon"],
                "layer_color": layer_meta["color"],
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("rotation_rel", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df


def build_ai_ranking_chart(combined: pd.DataFrame, layers_config=None) -> go.Figure:
    """Horizontal bar chart of all subcategories, colored by layer."""
    if layers_config is None:
        layers_config = AI_LAYERS
    if combined.empty:
        return go.Figure()

    sorted_df = combined.sort_values("rotation_rel", ascending=True).reset_index(drop=True)
    n = len(sorted_df)

    labels = [f"{n - i}. {row['industry']}" for i, row in sorted_df.iterrows()]
    colors = [row["layer_color"] for _, row in sorted_df.iterrows()]

    fig = go.Figure()

    # Single bar trace with per-bar colors
    fig.add_trace(go.Bar(
        y=labels,
        x=sorted_df["rotation_rel"],
        orientation="h",
        marker_color=colors,
        showlegend=False,
        customdata=sorted_df[["layer_name"]].values,
        hovertemplate="%{y}<br>Rotation: %{x:.3f}<br>Layer: %{customdata[0]}<extra></extra>",
    ))

    # No Plotly legend — rendered via Streamlit instead

    max_abs = max(
        abs(sorted_df["rotation_rel"].min()),
        abs(sorted_df["rotation_rel"].max()), 0.3) + 0.05

    fig.update_layout(
        height=max(500, n * 24),
        margin=dict(l=280, r=20, t=10, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=10),
        showlegend=False,
        xaxis=dict(gridcolor="#2d3148", zeroline=True,
                   zerolinecolor="#94a3b8", zerolinewidth=1.5,
                   range=[-max_abs, max_abs],
                   title="← Selling | Buying →",
                   title_font=dict(size=11, color="#94a3b8")),
        yaxis=dict(automargin=True, tickfont=dict(size=10)),
        bargap=0.3,
    )
    return fig


def render_ai_themes(ai_sector_results, ai_anomalies, ai_all_zscores,
                     weight_key="equal", layers_config=None, key_prefix="ai"):
    """Generic themes tab: combined ranking of all subcategories + drill-down."""
    if layers_config is None:
        layers_config = AI_LAYERS

    combined = _build_ai_combined_ranking(ai_sector_results, layers_config)
    if combined.empty:
        st.warning("No theme data available.")
        return

    # Build lookup: industry → layer_key
    ind_to_layer = dict(zip(combined["industry"], combined["layer_key"]))

    # Dropdown selector for subcategory
    industry_options = combined["industry"].tolist()
    dropdown_labels = {
        row["industry"]: f"{row['rank']}. {row['industry']}  ({layers_config[row['layer_key']]['icon']} {layers_config[row['layer_key']]['name']})"
        for _, row in combined.iterrows()
    }
    selected_industry = st.selectbox(
        "Select Subcategory", industry_options,
        format_func=lambda x: dropdown_labels.get(x, x),
        index=0, key=f"{key_prefix}_subcategory_select",
    )

    # Layer legend as HTML
    legend_items = []
    for lk, meta in layers_config.items():
        if lk in ind_to_layer.values():
            legend_items.append(
                f'<span style="display:inline-block; margin-right:18px; white-space:nowrap;">'
                f'<span style="display:inline-block; width:12px; height:12px; '
                f'background:{meta["color"]}; border-radius:2px; margin-right:4px; '
                f'vertical-align:middle;"></span>'
                f'<span style="vertical-align:middle; font-size:13px; color:#e2e8f0;">'
                f'{meta["icon"]} {meta["name"]}</span></span>'
            )
    st.markdown(
        f'<div style="margin-bottom:8px; line-height:2;">{"".join(legend_items)}</div>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        fig = build_ai_ranking_chart(combined, layers_config)
        event = st.plotly_chart(
            fig, use_container_width=True, key=f"{key_prefix}_ranking",
            on_select="rerun",
            config={"displayModeBar": False},
        )

    # Bar click overrides dropdown
    if event and event.selection and event.selection.points:
        point = event.selection.points[0]
        label = point.get("y", "")
        if isinstance(label, str) and ". " in label:
            clicked = label.split(". ", 1)[1]
            if clicked in ind_to_layer:
                selected_industry = clicked

    # Find which layer this industry belongs to
    selected_layer = ind_to_layer.get(selected_industry)

    with col_right:
        if selected_industry and selected_layer:
            sector = ai_sector_results[selected_layer]
            layer_meta = layers_config[selected_layer]

            st.markdown(
                f"### {layer_meta['icon']} {selected_industry}")

            ts = sector["time_series"].get(selected_industry)
            if ts is not None and not ts.empty:
                st.plotly_chart(build_timeseries_chart(ts), use_container_width=True)

            ind_info = combined[combined["industry"] == selected_industry]
            if not ind_info.empty:
                intra = ind_info.iloc[0]["rotation_rel"]
                st.markdown(
                    f'<div class="stock-header">'
                    f'Stocks (latest week) | Rotation: {intra:.3f} · '
                    f'Layer: {layer_meta["name"]}</div>',
                    unsafe_allow_html=True,
                )

            stocks = sector["stock_detail"].get(selected_industry)
            if stocks is not None and not stocks.empty:
                search = st.text_input(
                    "Search ticker", placeholder="Search ticker...",
                    label_visibility="collapsed", key=f"{key_prefix}_search",
                )

                display_df = stocks.copy().sort_values("rotation", ascending=False)
                if search:
                    display_df = display_df[
                        display_df["ticker"].str.contains(search.upper())]

                if weight_key == "market_cap":
                    total_dv = display_df["dollar_volume"].sum()
                    if total_dv > 0:
                        display_df["weight"] = (display_df["dollar_volume"] / total_dv * 100).round(1)
                    else:
                        display_df["weight"] = round(100.0 / len(display_df), 1)
                else:
                    display_df["weight"] = round(100.0 / len(display_df), 1)

                display_df = display_df.rename(columns={
                    "ticker": "Ticker",
                    "weight": "Weight %",
                    "rotation": "Capital Rotation Rel",
                    "trend": "Capital Trend Self",
                    "last_close": "Last Week Close",
                    "weekly_change_pct": "Weekly Change %",
                })

                show_cols = ["Ticker", "Weight %", "Capital Rotation Rel",
                             "Capital Trend Self", "Last Week Close", "Weekly Change %"]
                display_df = display_df[show_cols].copy()

                display_df["Capital Rotation Rel"] = display_df["Capital Rotation Rel"].round(2)
                display_df["Capital Trend Self"] = display_df["Capital Trend Self"].round(2)
                display_df["Last Week Close"] = display_df["Last Week Close"].round(2)
                display_df["Weekly Change %"] = display_df["Weekly Change %"].apply(
                    lambda v: f"{v:+.2f}%")

                st.dataframe(
                    display_df, use_container_width=True, hide_index=True,
                    height=min(400, 35 * len(display_df) + 38),
                    column_config={
                        "Weekly Change %": st.column_config.TextColumn("Weekly Change %"),
                    },
                )

    # Stock fund flow charts grid
    if selected_industry and selected_layer:
        sector = ai_sector_results[selected_layer]
        stock_ts = sector.get("stock_daily_rotation", {}).get(selected_industry, {})
        if stock_ts:
            st.markdown("---")
            st.markdown(f"### Stock Fund Flow — {selected_industry}")
            st.caption("Daily net fund flow for each stock (5-day rolling window, dollar-weighted)")

            sorted_tickers = []
            for ticker, ts_df in stock_ts.items():
                if not ts_df.empty and "net_flow" in ts_df.columns:
                    latest = ts_df["net_flow"].iloc[-1]
                    sorted_tickers.append((ticker, latest, ts_df))
            sorted_tickers.sort(key=lambda x: x[1], reverse=True)

            for i in range(0, len(sorted_tickers), 3):
                cols = st.columns(3, gap="small")
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(sorted_tickers):
                        break
                    ticker, _, ts_df = sorted_tickers[idx]
                    with col:
                        st.plotly_chart(
                            build_stock_flow_chart(ts_df, ticker),
                            use_container_width=True,
                        )

    # Heatmap: all subcategories over time
    st.markdown("---")
    tab_label = "All Subcategories"
    st.markdown(f"### Capital Rotation Heatmap — {tab_label}")
    st.caption("Rows sorted by latest rotation · Green = buying · Red = selling · Weekly data")
    st.plotly_chart(
        build_ai_heatmap(ai_sector_results, combined, layers_config),
        use_container_width=True,
    )


def build_ai_heatmap(ai_sector_results, combined_ranking, layers_config=None):
    """
    Heatmap: rows = subcategories grouped by layer,
    columns = weeks, color = rotation value.
    """
    if layers_config is None:
        layers_config = AI_LAYERS
    if combined_ranking.empty:
        return go.Figure()

    # Sort by layer order first, then by rotation within each layer (descending)
    layer_order = {k: i for i, k in enumerate(layers_config.keys())}
    sorted_ranking = combined_ranking.copy()
    sorted_ranking["layer_order"] = sorted_ranking["layer_key"].map(layer_order)
    sorted_ranking = sorted_ranking.sort_values(
        ["layer_order", "rotation_rel"], ascending=[True, False]
    ).reset_index(drop=True)

    # Collect weekly time series for each subcategory
    rows_data = []
    for _, row in sorted_ranking.iterrows():
        layer_key = row["layer_key"]
        industry = row["industry"]
        sector = ai_sector_results.get(layer_key, {})
        ts = sector.get("time_series", {}).get(industry)
        if ts is not None and not ts.empty:
            rows_data.append({
                "industry": industry,
                "layer_key": layer_key,
                "ts": ts,
                "latest_rot": row["rotation_rel"],
            })

    if not rows_data:
        return go.Figure()

    # Get union of all dates
    all_dates = sorted(set(
        d for r in rows_data for d in r["ts"]["date"].tolist()
    ))

    # Build the z-matrix and multicategory y-axis
    z = []
    y_categories = []  # (layer_name, subcategory) pairs for multicategory axis
    hover_text = []

    for r in rows_data:
        layer_meta = layers_config[r["layer_key"]]
        layer_label = f"{layer_meta['icon']} {layer_meta['name']}"
        y_categories.append((layer_label, r["industry"]))
        ts_indexed = r["ts"].set_index("date")["rotation_rel"]

        row_vals = []
        row_hover = []
        for d in all_dates:
            if d in ts_indexed.index:
                v = ts_indexed[d]
                row_vals.append(v)
                row_hover.append(
                    f"<b>{r['industry']}</b><br>"
                    f"{layer_meta['name']}<br>"
                    f"{d.strftime('%Y-%m-%d')}<br>"
                    f"Rotation: {v:.3f}")
            else:
                row_vals.append(None)
                row_hover.append("")
        z.append(row_vals)
        hover_text.append(row_hover)

    # Format x-axis dates
    x_labels = [d.strftime("%m/%d") for d in all_dates]

    # Multicategory y-axis: [layer_names], [subcategory_names]
    y_layer_names = [c[0] for c in y_categories]
    y_sub_names = [c[1] for c in y_categories]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=x_labels,
        y=[y_layer_names, y_sub_names],
        hovertext=hover_text,
        hoverinfo="text",
        colorscale=[
            [0.0, "#dc2626"],
            [0.3, "#f87171"],
            [0.5, "#f1f5f9"],
            [0.7, "#34d399"],
            [1.0, "#059669"],
        ],
        zmid=0, zmin=-1, zmax=1,
        colorbar=dict(
            title="Rotation",
            titleside="right",
            tickvals=[-1, -0.5, 0, 0.5, 1],
            ticktext=["-1.0", "-0.5", "0", "+0.5", "+1.0"],
            len=0.5, thickness=12,
        ),
        xgap=1, ygap=2,
    ))

    fig.update_layout(
        height=max(600, len(y_categories) * 26 + 100),
        margin=dict(l=10, r=60, t=30, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=10),
        xaxis=dict(
            tickangle=-45, tickfont=dict(size=9),
            side="top",
        ),
        yaxis=dict(
            automargin=True,
            tickfont=dict(size=10),
        ),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(
        '<div class="main-title">SmartMoney — Capital Rotation by Industry</div>',
        unsafe_allow_html=True,
    )

    # Load data (shared across tabs)
    all_data = load_all_data()
    n_tickers = all_data["n_tickers"]

    # Weighting toggle
    col_sub, col_toggle = st.columns([3, 1])
    with col_sub:
        st.markdown(
            f'<div class="subtitle">'
            f'Latest week: {datetime.now().strftime("%Y-%m-%d")} · '
            f'20w lookback · 5d rotation window</div>',
            unsafe_allow_html=True,
        )
    with col_toggle:
        weighting = st.toggle("Market-Cap Weighted", value=False)

    weight_key = "market_cap" if weighting else "equal"
    sector_results = all_data[weight_key]["sector_results"]
    anomalies = all_data[weight_key]["anomalies"]
    all_zscores = all_data[weight_key]["all_zscores"]

    ai_weight_key = "ai_market_cap" if weighting else "ai_equal"
    ai_sector_results = all_data[ai_weight_key]["sector_results"]
    ai_anomalies = all_data[ai_weight_key]["anomalies"]
    ai_all_zscores = all_data[ai_weight_key]["all_zscores"]

    pai_weight_key = "pai_market_cap" if weighting else "pai_equal"
    pai_sector_results = all_data[pai_weight_key]["sector_results"]
    pai_anomalies = all_data[pai_weight_key]["anomalies"]
    pai_all_zscores = all_data[pai_weight_key]["all_zscores"]

    # Top tabs
    tab_overview, tab_breakdown, tab_ai, tab_pai = st.tabs(
        ["Overview", "Sector Breakdown", "AI Themes", "Physical AI"])

    with tab_overview:
        render_overview(sector_results, anomalies, all_zscores)

    with tab_breakdown:
        render_sector_breakdown(sector_results, anomalies, weight_key)

    with tab_ai:
        render_ai_themes(ai_sector_results, ai_anomalies, ai_all_zscores,
                         weight_key, layers_config=AI_LAYERS, key_prefix="ai")

    with tab_pai:
        render_ai_themes(pai_sector_results, pai_anomalies, pai_all_zscores,
                         weight_key, layers_config=PAI_LAYERS, key_prefix="pai")

    # Footer
    st.markdown("---")
    st.caption(
        f"SmartMoney v0.1 · {n_tickers} tickers · "
        f"{'Market-Cap Weighted' if weighting else 'Equal Weighted'} · "
        f"Part of the [Investment Insights Toolkit](https://github.com/hong-chu) · "
        f"Data refreshes daily at market close"
    )
    st.caption(
        "Built by [Hong Chu](https://www.linkedin.com/in/hong-chu-quantai/) · "
        "Contact: yeesun.ch@gmail.com"
    )


if __name__ == "__main__":
    main()
