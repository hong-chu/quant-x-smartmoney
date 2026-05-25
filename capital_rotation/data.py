"""
Data fetching layer.

Fetches OHLCV data for all tickers across industry groups.
Uses yfinance by default with caching support.
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _cache_path(cache_dir: str, key: str) -> Path:
    """Generate a cache file path for a given key."""
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return Path(cache_dir) / f"{h}.parquet"


def fetch_ohlcv_batch(
    tickers: list[str],
    lookback_days: int = 100,
    provider: str = "yfinance",
    cache_dir: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for a batch of tickers.

    Returns dict of {ticker: DataFrame} with columns:
        date, open, high, low, close, volume
    """
    import yfinance as yf

    results = {}
    today = datetime.now().strftime("%Y-%m-%d")

    # Check cache first
    cached = set()
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        for ticker in tickers:
            cp = _cache_path(cache_dir, f"ohlcv_{ticker}_{today}_{lookback_days}")
            if cp.exists():
                try:
                    df = pd.read_parquet(cp)
                    if len(df) > 5:
                        results[ticker] = df
                        cached.add(ticker)
                except Exception:
                    pass

    remaining = [t for t in tickers if t not in cached]
    if cached:
        logger.info(f"  Loaded {len(cached)} tickers from cache")

    if not remaining:
        return results

    # Batch download with yfinance
    logger.info(f"  Downloading {len(remaining)} tickers...")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    try:
        data = yf.download(
            remaining,
            start=start_date,
            end=today,
            group_by="ticker",
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.error(f"  yfinance download failed: {e}")
        return results

    # Parse results
    for ticker in remaining:
        try:
            if len(remaining) == 1:
                df = data.copy()
            else:
                df = data[ticker].copy()

            df = df.dropna(subset=["Close"])
            if df.empty or len(df) < 5:
                continue

            df = df.reset_index()
            # Handle multi-level columns from yfinance
            if hasattr(df.columns, 'levels'):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            df.columns = [c.lower().replace(" ", "_") for c in df.columns]

            # Ensure we have required columns
            rename_map = {}
            for col in df.columns:
                if "date" in col or "timestamp" in col:
                    rename_map[col] = "date"

            if rename_map:
                df = df.rename(columns=rename_map)

            if "date" not in df.columns:
                df["date"] = df.index

            df["date"] = pd.to_datetime(df["date"])

            # Keep only needed columns
            keep_cols = ["date", "open", "high", "low", "close", "volume"]
            available = [c for c in keep_cols if c in df.columns]
            df = df[available].copy()

            if len(df) < 5:
                continue

            results[ticker] = df

            # Cache
            if cache_dir:
                cp = _cache_path(cache_dir, f"ohlcv_{ticker}_{today}_{lookback_days}")
                df.to_parquet(cp, index=False)

        except Exception as e:
            logger.debug(f"  Failed to parse {ticker}: {e}")
            continue

    return results


def compute_weekly_ohlcv(daily_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Resample daily OHLCV to weekly bars.

    Returns dict of {ticker: weekly_DataFrame}.
    """
    results = {}

    for ticker, df in daily_data.items():
        try:
            df = df.set_index("date").sort_index()

            weekly = df.resample("W-FRI").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna()

            if len(weekly) < 4:
                continue

            weekly = weekly.reset_index()
            results[ticker] = weekly

        except Exception as e:
            logger.debug(f"  Failed weekly resample for {ticker}: {e}")
            continue

    return results
