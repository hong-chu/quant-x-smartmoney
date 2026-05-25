"""
Interactive HTML Report Generator.

Generates a self-contained HTML report with:
  1. Sector selector dropdown
  2. Industry ranking bar chart (horizontal, green/red)
  3. Time series chart for selected industry
  4. Stock-level detail table for selected industry
  5. Anomaly highlights
"""

import json
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def generate_report(
    sector_data: dict[str, dict],
    anomalies: pd.DataFrame,
    config_summary: dict,
    output_path: str = "capital_rotation_report.html",
) -> str:
    """
    Generate the interactive HTML report.

    Args:
        sector_data: {
            etf: {
                "name": sector_name,
                "ranking": DataFrame (industry, rotation_rel, trend, rank),
                "time_series": {industry: DataFrame (date, rotation_rel)},
                "stock_detail": {industry: DataFrame (ticker, rotation, trend, ...)},
            }
        }
        anomalies: DataFrame of anomalous industries
        config_summary: dict of pipeline config for footer
        output_path: where to write the HTML

    Returns:
        Path to the generated report
    """
    # Prepare JSON data for the JavaScript frontend
    js_data = _prepare_js_data(sector_data, anomalies)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Capital Rotation by Industry</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
{_css()}
</style>
</head>
<body>

<div class="container">
    <header>
        <h1>Capital Rotation by Industry</h1>
        <p class="subtitle">Latest week: {datetime.now().strftime('%Y-%m-%d')} &middot;
            {config_summary.get('lookback_weeks', 20)}w lookback &middot;
            {config_summary.get('rotation_window', 5)}d rotation window</p>
    </header>

    <div class="controls">
        <label for="etf-select">Select ETF (Sector):</label>
        <select id="etf-select"></select>
        <span id="sector-label" class="sector-label"></span>
    </div>

    <div class="main-grid">
        <div class="panel ranking-panel">
            <h2>Capital Rotation by Industry</h2>
            <div id="ranking-chart"></div>
        </div>
        <div class="panel detail-panel">
            <div id="industry-title" class="industry-title"></div>
            <div id="timeseries-chart"></div>
            <div class="stock-table-wrap">
                <div id="stock-table-header" class="stock-header"></div>
                <input type="text" id="ticker-search" placeholder="Search ticker..."
                       class="ticker-search" />
                <div id="stock-table"></div>
            </div>
        </div>
    </div>

    {_anomaly_section_html(anomalies)}

    <footer>
        <p>Capital Rotation Report &middot; Part of the
        <a href="https://github.com/hong-chu">Investment Insights Toolkit</a>
        &middot; Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </footer>
</div>

<script>
{_javascript(js_data)}
</script>

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def _prepare_js_data(
    sector_data: dict[str, dict],
    anomalies: pd.DataFrame,
) -> str:
    """Convert Python data structures to JSON for the JS frontend."""
    data = {}

    for etf, sdata in sector_data.items():
        sector_entry = {
            "name": sdata["name"],
            "industries": [],
            "time_series": {},
            "stock_detail": {},
        }

        # Ranking data
        ranking = sdata.get("ranking", pd.DataFrame())
        if not ranking.empty:
            for _, row in ranking.iterrows():
                sector_entry["industries"].append({
                    "name": row["industry"],
                    "rotation_rel": round(float(row["rotation_rel"]), 4),
                    "trend": round(float(row["trend"]), 4),
                    "n_stocks": int(row["n_stocks"]),
                    "rank": int(row["rank"]),
                })

        # Time series per industry
        ts_data = sdata.get("time_series", {})
        for industry, ts_df in ts_data.items():
            if ts_df.empty:
                continue
            sector_entry["time_series"][industry] = {
                "dates": ts_df["date"].dt.strftime("%Y-%m-%d").tolist(),
                "values": [round(float(v), 4) for v in ts_df["rotation_rel"].tolist()],
            }

        # Stock detail per industry
        sd_data = sdata.get("stock_detail", {})
        for industry, sd_df in sd_data.items():
            if sd_df.empty:
                continue
            stocks = []
            for _, row in sd_df.iterrows():
                stocks.append({
                    "ticker": row["ticker"],
                    "rotation": round(float(row["rotation"]), 2),
                    "trend": round(float(row["trend"]), 4) if not pd.isna(row["trend"]) else 0,
                    "last_close": round(float(row["last_close"]), 2),
                    "weekly_change_pct": round(float(row["weekly_change_pct"]) * 100, 2),
                })
            sector_entry["stock_detail"][industry] = stocks

        data[etf] = sector_entry

    # Anomaly data
    anomaly_list = []
    if not anomalies.empty:
        for _, row in anomalies.iterrows():
            anomaly_list.append({
                "industry": row["industry"],
                "rotation_rel": round(float(row["rotation_rel"]), 4),
                "zscore": round(float(row["zscore"]), 2),
                "direction": row["direction"],
            })

    return json.dumps({"sectors": data, "anomalies": anomaly_list})


def _anomaly_section_html(anomalies: pd.DataFrame) -> str:
    """Generate the anomaly highlight section."""
    if anomalies.empty:
        return ""

    inflows = anomalies[anomalies["direction"] == "inflow_surge"]
    outflows = anomalies[anomalies["direction"] == "outflow_surge"]

    html = '<div class="anomaly-section">'
    html += '<h2>Rotation Anomalies</h2>'
    html += '<p class="anomaly-subtitle">Industries with statistically unusual rotation changes</p>'
    html += '<div class="anomaly-grid">'

    if not inflows.empty:
        html += '<div class="anomaly-col inflow">'
        html += '<h3>Unusual Inflow</h3>'
        for _, row in inflows.iterrows():
            html += f'''<div class="anomaly-card inflow">
                <span class="anomaly-name">{row["industry"]}</span>
                <span class="anomaly-score">Z: {row["zscore"]:.2f}</span>
                <span class="anomaly-rotation">Rotation: {row["rotation_rel"]:.1%}</span>
            </div>'''
        html += '</div>'

    if not outflows.empty:
        html += '<div class="anomaly-col outflow">'
        html += '<h3>Unusual Outflow</h3>'
        for _, row in outflows.iterrows():
            html += f'''<div class="anomaly-card outflow">
                <span class="anomaly-name">{row["industry"]}</span>
                <span class="anomaly-score">Z: {row["zscore"]:.2f}</span>
                <span class="anomaly-rotation">Rotation: {row["rotation_rel"]:.1%}</span>
            </div>'''
        html += '</div>'

    html += '</div></div>'
    return html


def _css() -> str:
    return """
:root {
    --bg: #0f1117;
    --surface: #1a1d29;
    --surface2: #232738;
    --border: #2d3148;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --green: #34d399;
    --red: #f87171;
    --blue: #60a5fa;
    --purple: #a78bfa;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
}

.container {
    max-width: 1440px;
    margin: 0 auto;
    padding: 24px;
}

header {
    margin-bottom: 24px;
}

h1 {
    font-size: 28px;
    font-weight: 700;
}

.subtitle {
    color: var(--text-dim);
    font-size: 14px;
    margin-top: 4px;
}

.controls {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding: 12px 16px;
    background: var(--surface);
    border-radius: 8px;
    border: 1px solid var(--border);
}

.controls label {
    font-size: 14px;
    color: var(--text-dim);
}

.controls select {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 14px;
    cursor: pointer;
}

.sector-label {
    font-size: 14px;
    color: var(--blue);
    margin-left: 8px;
}

.main-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
}

.panel {
    background: var(--surface);
    border-radius: 10px;
    border: 1px solid var(--border);
    padding: 20px;
    overflow: hidden;
}

.panel h2 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--text);
}

.industry-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 12px;
    min-height: 28px;
}

.stock-table-wrap {
    margin-top: 16px;
}

.stock-header {
    font-size: 14px;
    color: var(--text-dim);
    margin-bottom: 8px;
}

.ticker-search {
    width: 200px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    color: var(--text);
    font-size: 13px;
    margin-bottom: 8px;
}

.ticker-search::placeholder {
    color: var(--text-dim);
}

#stock-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

#stock-table th {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 2px solid var(--border);
    color: var(--text-dim);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
    cursor: pointer;
    user-select: none;
}

#stock-table th:hover {
    color: var(--text);
}

#stock-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
}

#stock-table tr:hover {
    background: var(--surface2);
}

#stock-table .ticker-cell {
    font-weight: 600;
}

.positive { color: var(--green); }
.negative { color: var(--red); }

/* Anomaly Section */
.anomaly-section {
    margin-top: 24px;
    padding: 24px;
    background: var(--surface);
    border-radius: 10px;
    border: 1px solid var(--border);
}

.anomaly-section h2 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 4px;
}

.anomaly-subtitle {
    color: var(--text-dim);
    font-size: 13px;
    margin-bottom: 16px;
}

.anomaly-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.anomaly-col h3 {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 10px;
}

.anomaly-col.inflow h3 { color: var(--green); }
.anomaly-col.outflow h3 { color: var(--red); }

.anomaly-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: var(--surface2);
    border-radius: 6px;
    margin-bottom: 6px;
    border-left: 3px solid;
}

.anomaly-card.inflow { border-left-color: var(--green); }
.anomaly-card.outflow { border-left-color: var(--red); }

.anomaly-name {
    flex: 1;
    font-weight: 500;
    font-size: 13px;
}

.anomaly-score {
    font-weight: 600;
    font-size: 13px;
}

.anomaly-card.inflow .anomaly-score { color: var(--green); }
.anomaly-card.outflow .anomaly-score { color: var(--red); }

.anomaly-rotation {
    color: var(--text-dim);
    font-size: 12px;
}

/* Ranking bar highlight */
.ranking-panel {
    overflow-y: auto;
    max-height: 800px;
}

footer {
    margin-top: 40px;
    padding: 20px;
    text-align: center;
    color: var(--text-dim);
    font-size: 12px;
    border-top: 1px solid var(--border);
}

footer a {
    color: var(--blue);
    text-decoration: none;
}
"""


def _javascript(js_data: str) -> str:
    return f"""
const DATA = {js_data};
let currentETF = null;
let currentIndustry = null;
let sortCol = null;
let sortAsc = true;

// Initialize
function init() {{
    const select = document.getElementById('etf-select');
    const etfs = Object.keys(DATA.sectors);

    etfs.forEach(etf => {{
        const opt = document.createElement('option');
        opt.value = etf;
        opt.textContent = etf + ' - ' + DATA.sectors[etf].name;
        select.appendChild(opt);
    }});

    select.addEventListener('change', () => selectSector(select.value));

    // Default to XLK
    if (etfs.includes('XLK')) {{
        select.value = 'XLK';
        selectSector('XLK');
    }} else if (etfs.length > 0) {{
        selectSector(etfs[0]);
    }}

    // Ticker search
    document.getElementById('ticker-search').addEventListener('input', (e) => {{
        filterStockTable(e.target.value);
    }});
}}

function selectSector(etf) {{
    currentETF = etf;
    const sector = DATA.sectors[etf];
    document.getElementById('sector-label').textContent = 'Sector: ' + sector.name;

    renderRankingChart(sector);

    // Auto-select top industry
    if (sector.industries.length > 0) {{
        selectIndustry(sector.industries[0].name);
    }}
}}

function renderRankingChart(sector) {{
    const industries = sector.industries;
    if (!industries.length) return;

    // Sort by rotation (already sorted, but ensure)
    const sorted = [...industries].sort((a, b) => a.rotation_rel - b.rotation_rel);

    const colors = sorted.map(d => d.rotation_rel >= 0.5 ? '#34d399' : '#f87171');

    const trace = {{
        type: 'bar',
        orientation: 'h',
        y: sorted.map((d, i) => (sorted.length - i) + '. ' + d.name),
        x: sorted.map(d => d.rotation_rel),
        marker: {{ color: colors }},
        hovertemplate: '%{{y}}<br>Rotation: %{{x:.3f}}<extra></extra>',
    }};

    const layout = {{
        margin: {{ l: 250, r: 20, t: 10, b: 30 }},
        height: Math.max(400, sorted.length * 28),
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: {{ color: '#e2e8f0', size: 11 }},
        xaxis: {{
            gridcolor: '#2d3148',
            zeroline: true,
            zerolinecolor: '#4a5568',
            range: [0, Math.max(0.7, Math.max(...sorted.map(d => d.rotation_rel)) + 0.05)],
        }},
        yaxis: {{
            automargin: true,
        }},
        bargap: 0.3,
    }};

    Plotly.newPlot('ranking-chart', [trace], layout, {{
        displayModeBar: false,
        responsive: true,
    }});

    // Click handler on bars
    document.getElementById('ranking-chart').on('plotly_click', (data) => {{
        const label = data.points[0].y;
        const name = label.replace(/^\\d+\\.\\s*/, '');
        selectIndustry(name);
    }});
}}

function selectIndustry(name) {{
    currentIndustry = name;
    const sector = DATA.sectors[currentETF];

    document.getElementById('industry-title').textContent = name;

    // Render time series
    const ts = sector.time_series[name];
    if (ts) {{
        renderTimeSeries(name, ts);
    }}

    // Render stock table
    const stocks = sector.stock_detail[name];
    if (stocks) {{
        renderStockTable(stocks, name);
    }}
}}

function renderTimeSeries(name, ts) {{
    const colors = ts.values.map(v => v >= 0.5 ? '#34d399' : '#f87171');

    const trace = {{
        type: 'bar',
        x: ts.dates,
        y: ts.values,
        marker: {{ color: colors }},
        hovertemplate: '%{{x}}<br>Rotation: %{{y:.3f}}<extra></extra>',
    }};

    const layout = {{
        margin: {{ l: 50, r: 20, t: 10, b: 50 }},
        height: 250,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: {{ color: '#e2e8f0', size: 11 }},
        xaxis: {{
            gridcolor: '#2d3148',
            tickangle: -45,
        }},
        yaxis: {{
            title: 'Capital Rotation Rel',
            gridcolor: '#2d3148',
            range: [0, 0.7],
        }},
        bargap: 0.15,
    }};

    Plotly.newPlot('timeseries-chart', [trace], layout, {{
        displayModeBar: false,
        responsive: true,
    }});
}}

function renderStockTable(stocks, industryName) {{
    // Find industry info for intra score
    const sector = DATA.sectors[currentETF];
    const industryInfo = sector.industries.find(i => i.name === industryName);
    const intraScore = industryInfo ? industryInfo.rotation_rel : 0;

    document.getElementById('stock-table-header').textContent =
        'Stocks (latest week) | Intra.: ' + intraScore.toFixed(3);

    const sortedStocks = sortStocks(stocks);

    let html = '<table>';
    html += '<thead><tr>';
    html += '<th data-col="ticker" onclick="sortTable(\\'ticker\\')">Ticker</th>';
    html += '<th data-col="rotation" onclick="sortTable(\\'rotation\\')">Capital Rotation Rel</th>';
    html += '<th data-col="trend" onclick="sortTable(\\'trend\\')">Capital Trend Self</th>';
    html += '<th data-col="last_close" onclick="sortTable(\\'last_close\\')">Last Week Close</th>';
    html += '<th data-col="weekly_change_pct" onclick="sortTable(\\'weekly_change_pct\\')">Weekly Change %</th>';
    html += '</tr></thead><tbody>';

    sortedStocks.forEach(s => {{
        const changeClass = s.weekly_change_pct >= 0 ? 'positive' : 'negative';
        const changeSign = s.weekly_change_pct >= 0 ? '+' : '';
        html += '<tr>';
        html += '<td class="ticker-cell">' + s.ticker + '</td>';
        html += '<td>' + s.rotation.toFixed(2) + '</td>';
        html += '<td>' + s.trend.toFixed(2) + '</td>';
        html += '<td>' + s.last_close.toFixed(2) + '</td>';
        html += '<td class="' + changeClass + '">' + changeSign + s.weekly_change_pct.toFixed(2) + '%</td>';
        html += '</tr>';
    }});

    html += '</tbody></table>';
    document.getElementById('stock-table').innerHTML = html;
}}

function sortStocks(stocks) {{
    if (!sortCol) return stocks;
    return [...stocks].sort((a, b) => {{
        let va = a[sortCol], vb = b[sortCol];
        if (typeof va === 'string') {{
            return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        }}
        return sortAsc ? va - vb : vb - va;
    }});
}}

function sortTable(col) {{
    if (sortCol === col) {{
        sortAsc = !sortAsc;
    }} else {{
        sortCol = col;
        sortAsc = col === 'ticker';
    }}
    const sector = DATA.sectors[currentETF];
    const stocks = sector.stock_detail[currentIndustry];
    if (stocks) renderStockTable(stocks, currentIndustry);
}}

function filterStockTable(query) {{
    const rows = document.querySelectorAll('#stock-table tbody tr');
    const q = query.toUpperCase();
    rows.forEach(row => {{
        const ticker = row.cells[0]?.textContent || '';
        row.style.display = ticker.toUpperCase().includes(q) ? '' : 'none';
    }});
}}

// Start
document.addEventListener('DOMContentLoaded', init);
"""
