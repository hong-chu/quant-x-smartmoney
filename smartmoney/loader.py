"""
Shared data loader for Streamlit pages.

Centralizes data fetching and caching so all pages share the same data.
Computes both equal-weighted and market-cap-weighted rotation.

Supports two modes:
  1. Pre-cached: reads from data/cache.pkl (written by GitHub Actions)
  2. Live fetch: fetches from yfinance on-demand (fallback)
"""

import logging
import pickle
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

from smartmoney.taxonomy import TAXONOMY, SECTOR_ETFS
from smartmoney.data import fetch_ohlcv_batch, compute_weekly_ohlcv
from smartmoney.rotation import (
    calc_industry_rotation,
    calc_stock_rotation,
    rank_industries,
    get_stock_detail,
    calc_rotation_anomalies,
    calc_all_industry_zscores,
)

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "cache.pkl"


def _build_sector_results(daily_data, taxonomy, weighting):
    """Build sector results for a given weighting method."""
    sector_results = {}
    all_industry_rotations = {}

    for etf, industries in taxonomy.items():
        sector_name = SECTOR_ETFS.get(etf, etf)

        industry_rotations_daily = calc_industry_rotation(
            daily_data, industries, window=5, weighting=weighting,
        )

        # Resample daily rotation to weekly for time series
        industry_ts_weekly = {}
        industry_rotations_weekly = {}
        for ind_name, daily_df in industry_rotations_daily.items():
            if daily_df.empty:
                continue
            weekly_df = (daily_df.set_index("date")[["rotation_rel", "trend", "n_stocks"]]
                         .resample("W-FRI").mean().dropna().reset_index())
            if len(weekly_df) >= 2:
                industry_ts_weekly[ind_name] = weekly_df[["date", "rotation_rel"]]
                industry_rotations_weekly[ind_name] = weekly_df

        # Rank by latest weekly value (not daily)
        ranking = rank_industries(industry_rotations_weekly, etf)

        # Stock details + daily rotation per stock (weighting-independent)
        stock_details = {}
        stock_daily_rotation = {}
        for ind_name, tickers in industries.items():
            clean_name = ind_name.lstrip("*")
            sd = get_stock_detail(daily_data, tickers, window=5)
            if not sd.empty:
                stock_details[clean_name] = sd

            ind_stock_ts = {}
            for ticker in tickers:
                if ticker not in daily_data:
                    continue
                try:
                    rot = calc_stock_rotation(daily_data[ticker], window=5)
                    if not rot.empty:
                        ind_stock_ts[ticker] = rot[["date", "rotation", "net_flow"]].dropna()
                except Exception:
                    continue
            if ind_stock_ts:
                stock_daily_rotation[clean_name] = ind_stock_ts

        # Sector-level rotation time series
        sector_ts_rows = []
        all_dates = set()
        for df in industry_rotations_daily.values():
            if not df.empty:
                all_dates.update(df["date"].tolist())
        all_dates = sorted(all_dates)

        for date in all_dates:
            vals = []
            for df in industry_rotations_daily.values():
                match = df[df["date"] == date]
                if not match.empty:
                    v = match["rotation_rel"].iloc[0]
                    if not np.isnan(v):
                        vals.append(v)
            if vals:
                sector_ts_rows.append({"date": date, "rotation_rel": np.mean(vals)})

        sector_ts_daily = pd.DataFrame(sector_ts_rows)
        sector_ts_weekly_agg = pd.DataFrame()
        if not sector_ts_daily.empty:
            sector_ts_weekly_agg = (
                sector_ts_daily.set_index("date")[["rotation_rel"]]
                .resample("W-FRI").mean().dropna().reset_index()
            )

        sector_results[etf] = {
            "name": sector_name,
            "ranking": ranking,
            "time_series": industry_ts_weekly,
            "stock_detail": stock_details,
            "stock_daily_rotation": stock_daily_rotation,
            "sector_ts_weekly": sector_ts_weekly_agg,
        }

        for k, v in industry_rotations_daily.items():
            all_industry_rotations[k] = v

    all_zscores = calc_all_industry_zscores(all_industry_rotations)
    anomalies = calc_rotation_anomalies(all_industry_rotations)

    return sector_results, anomalies, all_zscores


@st.cache_data(ttl=86400, show_spinner="Loading market data...")
def load_all_data():
    """
    Load pre-computed data from cache.pkl (written by GitHub Actions).
    Falls back to live yfinance fetch if no cache exists.
    """
    # Try pre-computed cache first
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            updated = data.get("updated_at", "unknown")
            logger.info(f"Loaded pre-computed cache (updated: {updated})")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}, falling back to live fetch")

    # Fallback: live fetch from yfinance
    logger.info("No cache found — fetching live from yfinance...")
    return _fetch_live()


def _fetch_live():
    """Fetch live data from yfinance and compute all rotations."""
    all_tickers = set()
    for industries in TAXONOMY.values():
        for tickers in industries.values():
            all_tickers.update(tickers)

    daily_data = fetch_ohlcv_batch(
        list(all_tickers),
        lookback_days=140,
        cache_dir=".cache",
    )

    # Split taxonomy into sector ETFs vs AI themes vs Physical AI
    sector_taxonomy = {k: v for k, v in TAXONOMY.items()
                       if not k.startswith("AI_") and not k.startswith("PAI_")}
    ai_taxonomy = {k: v for k, v in TAXONOMY.items() if k.startswith("AI_")}
    pai_taxonomy = {k: v for k, v in TAXONOMY.items() if k.startswith("PAI_")}

    # Compute both weightings for sector ETFs
    eq_results, eq_anomalies, eq_zscores = _build_sector_results(
        daily_data, sector_taxonomy, "equal")
    mc_results, mc_anomalies, mc_zscores = _build_sector_results(
        daily_data, sector_taxonomy, "market_cap")

    # Compute both weightings for AI themes
    ai_eq_results, ai_eq_anomalies, ai_eq_zscores = _build_sector_results(
        daily_data, ai_taxonomy, "equal")
    ai_mc_results, ai_mc_anomalies, ai_mc_zscores = _build_sector_results(
        daily_data, ai_taxonomy, "market_cap")

    # Compute both weightings for Physical AI
    pai_eq_results, pai_eq_anomalies, pai_eq_zscores = _build_sector_results(
        daily_data, pai_taxonomy, "equal")
    pai_mc_results, pai_mc_anomalies, pai_mc_zscores = _build_sector_results(
        daily_data, pai_taxonomy, "market_cap")

    return {
        "equal": {
            "sector_results": eq_results,
            "anomalies": eq_anomalies,
            "all_zscores": eq_zscores,
        },
        "market_cap": {
            "sector_results": mc_results,
            "anomalies": mc_anomalies,
            "all_zscores": mc_zscores,
        },
        "ai_equal": {
            "sector_results": ai_eq_results,
            "anomalies": ai_eq_anomalies,
            "all_zscores": ai_eq_zscores,
        },
        "ai_market_cap": {
            "sector_results": ai_mc_results,
            "anomalies": ai_mc_anomalies,
            "all_zscores": ai_mc_zscores,
        },
        "pai_equal": {
            "sector_results": pai_eq_results,
            "anomalies": pai_eq_anomalies,
            "all_zscores": pai_eq_zscores,
        },
        "pai_market_cap": {
            "sector_results": pai_mc_results,
            "anomalies": pai_mc_anomalies,
            "all_zscores": pai_mc_zscores,
        },
        "n_tickers": len(daily_data),
    }
