"""
Capital Rotation Calculation.

Computes a "Capital Rotation" metric for each stock and aggregates
to the industry group level.

The rotation metric measures relative money flow intensity:
  - How much capital is flowing into/out of a stock relative to its norm
  - Aggregated to industry level by market-cap weighting or equal weighting

Two key metrics:
  1. Capital Rotation Rel — relative rotation score, normalized [0, 1]
     Higher = more capital rotating IN, lower = more rotating OUT
  2. Capital Trend Self — how the stock's own rotation is trending
     (is it accelerating or decelerating?)
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calc_stock_rotation(
    df: pd.DataFrame,
    window: int = 5,
) -> pd.DataFrame:
    """
    Calculate capital rotation metrics for a single stock.

    Uses volume-weighted price momentum as a proxy for capital rotation:
      - TP (Typical Price) = (H + L + C) / 3
      - If TP rises, volume = "inflow"; if TP falls, volume = "outflow"
      - Rotation = (inflow - outflow) / (inflow + outflow)  → [-1, 1]

    Args:
        df: OHLCV DataFrame with columns: date, open, high, low, close, volume
        window: Rolling window in bars (days or weeks)

    Returns:
        DataFrame with added columns: rotation, trend
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    # Typical Price
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3
    df["tp_change"] = df["tp"].diff()

    # Classify volume
    df["inflow"] = np.where(df["tp_change"] > 0, df["volume"], 0)
    df["outflow"] = np.where(df["tp_change"] < 0, df["volume"], 0)

    # Rolling sums
    df["inflow_sum"] = df["inflow"].rolling(window, min_periods=1).sum()
    df["outflow_sum"] = df["outflow"].rolling(window, min_periods=1).sum()
    total = df["inflow_sum"] + df["outflow_sum"]

    # Rotation ratio [-1, 1]: +1 = all buying, 0 = balanced, -1 = all selling
    df["rotation"] = np.where(total > 0, (df["inflow_sum"] - df["outflow_sum"]) / total, 0.0)

    # Net flow in dollar terms: (inflow - outflow) * typical price
    df["net_flow"] = (df["inflow_sum"] - df["outflow_sum"]) * df["tp"]

    # Trend: change in rotation over the window
    df["trend"] = df["rotation"].diff(window)

    return df


def calc_industry_rotation(
    stock_data: dict[str, pd.DataFrame],
    industry_tickers: dict[str, list[str]],
    window: int = 5,
    weighting: str = "equal",
) -> dict[str, pd.DataFrame]:
    """
    Calculate rotation metrics for each industry group.

    For each industry, computes:
      - rotation_rel: weighted average rotation across member stocks
      - stock-level detail for drill-down

    Args:
        stock_data: {ticker: OHLCV DataFrame}
        industry_tickers: {industry_name: [tickers]}
        window: Rolling window for rotation calculation
        weighting: "equal" for equal-weighted, "market_cap" for dollar-volume weighted

    Returns:
        {industry_name: DataFrame with daily rotation series}
    """
    industry_results = {}

    for industry, tickers in industry_tickers.items():
        clean_name = industry.lstrip("*")

        # Calculate rotation for each stock in the industry
        stock_rotations = {}
        for ticker in tickers:
            if ticker not in stock_data:
                continue
            df = stock_data[ticker]
            try:
                rot = calc_stock_rotation(df, window=window)
                stock_rotations[ticker] = rot
            except Exception as e:
                logger.debug(f"  Rotation calc failed for {ticker}: {e}")
                continue

        if not stock_rotations:
            continue

        # Align on date
        all_dates = set()
        for rot_df in stock_rotations.values():
            all_dates.update(rot_df["date"].tolist())
        all_dates = sorted(all_dates)

        rows = []
        for date in all_dates:
            rotations = []
            weights = []
            trends = []
            trend_weights = []

            for ticker, rot_df in stock_rotations.items():
                match = rot_df[rot_df["date"] == date]
                if not match.empty:
                    r = match["rotation"].iloc[0]
                    t = match["trend"].iloc[0]

                    if not np.isnan(r):
                        rotations.append(r)
                        if weighting == "market_cap":
                            # Dollar volume = close * volume as weight proxy
                            c = match["close"].iloc[0]
                            v = match["volume"].iloc[0]
                            w = c * v if (not np.isnan(c) and not np.isnan(v) and v > 0) else 1.0
                            weights.append(w)
                        else:
                            weights.append(1.0)

                    if not np.isnan(t):
                        trends.append(t)
                        if weighting == "market_cap":
                            c = match["close"].iloc[0]
                            v = match["volume"].iloc[0]
                            w = c * v if (not np.isnan(c) and not np.isnan(v) and v > 0) else 1.0
                            trend_weights.append(w)
                        else:
                            trend_weights.append(1.0)

            if rotations:
                w_arr = np.array(weights)
                w_norm = w_arr / w_arr.sum() if w_arr.sum() > 0 else np.ones_like(w_arr) / len(w_arr)
                weighted_rot = np.dot(rotations, w_norm)

                if trends:
                    tw_arr = np.array(trend_weights)
                    tw_norm = tw_arr / tw_arr.sum() if tw_arr.sum() > 0 else np.ones_like(tw_arr) / len(tw_arr)
                    weighted_trend = np.dot(trends, tw_norm)
                else:
                    weighted_trend = 0

                rows.append({
                    "date": date,
                    "rotation_rel": weighted_rot,
                    "trend": weighted_trend,
                    "n_stocks": len(rotations),
                })

        if rows:
            industry_df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
            industry_results[clean_name] = industry_df

    return industry_results


def rank_industries(
    industry_rotations: dict[str, pd.DataFrame],
    sector_etf: str,
) -> pd.DataFrame:
    """
    Rank industries within a sector by their latest rotation score.

    Returns DataFrame sorted by rotation_rel (descending):
        industry, rotation_rel, trend, n_stocks, rank
    """
    rows = []

    for industry, df in industry_rotations.items():
        if df.empty:
            continue

        latest = df.iloc[-1]
        rows.append({
            "industry": industry,
            "sector_etf": sector_etf,
            "rotation_rel": latest["rotation_rel"],
            "trend": latest["trend"],
            "n_stocks": latest["n_stocks"],
        })

    if not rows:
        return pd.DataFrame()

    ranking = pd.DataFrame(rows)
    ranking = ranking.sort_values("rotation_rel", ascending=False).reset_index(drop=True)
    ranking["rank"] = range(1, len(ranking) + 1)

    return ranking


def get_stock_detail(
    stock_data: dict[str, pd.DataFrame],
    tickers: list[str],
    window: int = 5,
) -> pd.DataFrame:
    """
    Get stock-level rotation detail for a specific industry group.

    Returns DataFrame with latest rotation metrics per stock:
        ticker, rotation, trend, last_close, weekly_change_pct, market_cap_approx
    """
    rows = []

    for ticker in tickers:
        if ticker not in stock_data:
            continue

        df = stock_data[ticker]
        try:
            rot = calc_stock_rotation(df, window=window)
            if rot.empty:
                continue

            latest = rot.iloc[-1]
            prev_week = rot.iloc[-window] if len(rot) > window else rot.iloc[0]

            weekly_change = (latest["close"] - prev_week["close"]) / prev_week["close"]

            # Dollar volume for market-cap weight proxy
            dollar_vol = latest["close"] * latest["volume"] if latest["volume"] > 0 else 0.0

            rows.append({
                "ticker": ticker,
                "rotation": latest["rotation"],
                "trend": latest["trend"],
                "last_close": latest["close"],
                "weekly_change_pct": weekly_change,
                "dollar_volume": dollar_vol,
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("rotation", ascending=False).reset_index(drop=True)


def calc_all_industry_zscores(
    industry_rotations: dict[str, pd.DataFrame],
    zscore_window: int = 12,
) -> pd.DataFrame:
    """
    Compute Z-score for ALL industries (not just anomalies).

    Returns DataFrame with one row per industry:
        industry, rotation_rel, zscore
    """
    rows = []

    for industry, df in industry_rotations.items():
        if len(df) < zscore_window + 1:
            continue

        recent = df["rotation_rel"].iloc[-1]
        history = df["rotation_rel"].iloc[-(zscore_window + 1):-1]

        if history.std() == 0:
            rows.append({
                "industry": industry,
                "rotation_rel": recent,
                "zscore": 0.0,
            })
        else:
            z = (recent - history.mean()) / history.std()
            rows.append({
                "industry": industry,
                "rotation_rel": recent,
                "zscore": z,
            })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("zscore", key=abs, ascending=False).reset_index(drop=True)


def calc_rotation_anomalies(
    industry_rotations: dict[str, pd.DataFrame],
    zscore_window: int = 12,
    threshold: float = 2.0,
) -> pd.DataFrame:
    """
    Detect industries with anomalous rotation changes.

    Computes Z-score on the latest rotation value vs. the trailing window.

    Returns DataFrame of anomalous industries:
        industry, rotation_rel, zscore, direction, sector_etf
    """
    all_zscores = calc_all_industry_zscores(industry_rotations, zscore_window)
    if all_zscores.empty:
        return pd.DataFrame()

    anomalies = all_zscores[all_zscores["zscore"].abs() > threshold].copy()
    if anomalies.empty:
        return pd.DataFrame()

    anomalies["direction"] = anomalies["zscore"].apply(
        lambda z: "inflow_surge" if z > 0 else "outflow_surge"
    )
    return anomalies.reset_index(drop=True)
