"""
Daily data prefetch script — run by GitHub Actions.

Fetches OHLCV for all tickers, computes rotation for all sectors/themes,
and saves the result as a pickle file for the Streamlit app to read.
"""

import sys
import pickle
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smartmoney.taxonomy import TAXONOMY, SECTOR_ETFS
from smartmoney.data import fetch_ohlcv_batch
from smartmoney.loader import _build_sector_results

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

CACHE_FILE = ROOT / "data" / "cache.pkl"


def main():
    logger.info("=== SmartMoney Daily Prefetch ===")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Collect all tickers
    all_tickers = set()
    for industries in TAXONOMY.values():
        for tickers in industries.values():
            all_tickers.update(tickers)

    logger.info(f"Total tickers: {len(all_tickers)}")

    # Fetch OHLCV data (no local cache dir — fresh fetch each time)
    daily_data = fetch_ohlcv_batch(
        list(all_tickers),
        lookback_days=140,
    )
    logger.info(f"Fetched {len(daily_data)} tickers successfully")

    if len(daily_data) < 50:
        logger.error(f"Only {len(daily_data)} tickers fetched — too few, aborting")
        sys.exit(1)

    # Split taxonomy
    sector_taxonomy = {k: v for k, v in TAXONOMY.items()
                       if not k.startswith("AI_") and not k.startswith("PAI_")}
    ai_taxonomy = {k: v for k, v in TAXONOMY.items() if k.startswith("AI_")}
    pai_taxonomy = {k: v for k, v in TAXONOMY.items() if k.startswith("PAI_")}

    # Compute all weightings
    logger.info("Computing sector rotations (equal)...")
    eq_results, eq_anomalies, eq_zscores = _build_sector_results(
        daily_data, sector_taxonomy, "equal")

    logger.info("Computing sector rotations (market_cap)...")
    mc_results, mc_anomalies, mc_zscores = _build_sector_results(
        daily_data, sector_taxonomy, "market_cap")

    logger.info("Computing AI theme rotations (equal)...")
    ai_eq_results, ai_eq_anomalies, ai_eq_zscores = _build_sector_results(
        daily_data, ai_taxonomy, "equal")

    logger.info("Computing AI theme rotations (market_cap)...")
    ai_mc_results, ai_mc_anomalies, ai_mc_zscores = _build_sector_results(
        daily_data, ai_taxonomy, "market_cap")

    logger.info("Computing Physical AI rotations (equal)...")
    pai_eq_results, pai_eq_anomalies, pai_eq_zscores = _build_sector_results(
        daily_data, pai_taxonomy, "equal")

    logger.info("Computing Physical AI rotations (market_cap)...")
    pai_mc_results, pai_mc_anomalies, pai_mc_zscores = _build_sector_results(
        daily_data, pai_taxonomy, "market_cap")

    result = {
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
        "updated_at": datetime.now().isoformat(),
    }

    # Save
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)

    size_mb = CACHE_FILE.stat().st_size / 1024 / 1024
    logger.info(f"Saved cache to {CACHE_FILE} ({size_mb:.1f} MB)")
    logger.info("=== Prefetch complete ===")


if __name__ == "__main__":
    main()
