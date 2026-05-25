#!/usr/bin/env python3
"""
SmartMoney — Industry-Level Capital Rotation Tracker

Ranks industries within each sector by capital rotation intensity,
detects anomalous rotation changes, and generates an interactive HTML report.

Usage:
    python main.py                          # all sectors
    python main.py --sectors XLK XLE        # Technology + Energy only
    python main.py --lookback 30            # 30 weeks of history
    python main.py --threshold 1.5          # lower anomaly threshold
    python main.py --custom-taxonomy my.json # extend industry groups

Part of the Investment Insights Toolkit.
"""

import argparse
import logging
import sys
from pathlib import Path

from smartmoney.config import RotationConfig
from smartmoney.taxonomy import (
    TAXONOMY, SECTOR_ETFS, load_custom_taxonomy,
    get_all_tickers,
)
from smartmoney.data import fetch_ohlcv_batch, compute_weekly_ohlcv
from smartmoney.rotation import (
    calc_stock_rotation,
    calc_industry_rotation,
    rank_industries,
    get_stock_detail,
    calc_rotation_anomalies,
)
from smartmoney.report import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Capital Rotation by Industry")
    p.add_argument("--sectors", nargs="*", default=None,
                   help="Sector ETFs to scan (e.g. XLK XLE). Default: all sectors")
    p.add_argument("--lookback", type=int, default=20,
                   help="Weeks of history (default: 20)")
    p.add_argument("--rotation-window", type=int, default=5,
                   help="Trading days for rotation metric (default: 5 = 1 week)")
    p.add_argument("--zscore-window", type=int, default=12,
                   help="Weeks for anomaly Z-score baseline (default: 12)")
    p.add_argument("--threshold", type=float, default=2.0,
                   help="Z-score anomaly threshold (default: 2.0)")
    p.add_argument("--custom-taxonomy", default=None,
                   help="Path to custom taxonomy JSON file")
    p.add_argument("--output", default="capital_rotation_report.html",
                   help="Output HTML file path")
    p.add_argument("--cache-dir", default=".cache",
                   help="Cache directory for fetched data")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Debug logging")
    return p.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # --- Load taxonomy ---
    taxonomy = TAXONOMY
    if args.custom_taxonomy:
        logger.info(f"Loading custom taxonomy from {args.custom_taxonomy}")
        taxonomy = load_custom_taxonomy(args.custom_taxonomy)

    # Filter sectors
    if args.sectors:
        valid = set(taxonomy.keys())
        for s in args.sectors:
            if s not in valid:
                logger.error(f"Unknown sector ETF: {s}. Available: {sorted(valid)}")
                sys.exit(1)
        sector_etfs = args.sectors
    else:
        sector_etfs = list(taxonomy.keys())

    logger.info(f"Scanning {len(sector_etfs)} sectors: {', '.join(sector_etfs)}")

    # --- Collect all tickers ---
    all_tickers = set()
    for etf in sector_etfs:
        for tickers in taxonomy[etf].values():
            all_tickers.update(tickers)

    logger.info(f"Total tickers to fetch: {len(all_tickers)}")

    # --- Fetch data ---
    lookback_days = args.lookback * 7  # convert weeks to approximate calendar days
    logger.info(f"Step 1/4: Fetching OHLCV data ({lookback_days} days)...")
    daily_data = fetch_ohlcv_batch(
        list(all_tickers),
        lookback_days=lookback_days,
        cache_dir=args.cache_dir,
    )
    logger.info(f"  Got data for {len(daily_data)}/{len(all_tickers)} tickers")

    if len(daily_data) < 5:
        logger.error("Too few tickers returned. Check your network connection.")
        sys.exit(1)

    # --- Compute weekly data ---
    logger.info("Step 2/4: Computing weekly bars...")
    weekly_data = compute_weekly_ohlcv(daily_data)
    logger.info(f"  Weekly data for {len(weekly_data)} tickers")

    # --- Calculate rotation by sector ---
    logger.info("Step 3/4: Calculating industry rotation...")
    sector_results = {}
    all_industry_rotations = {}

    for etf in sector_etfs:
        sector_name = SECTOR_ETFS.get(etf, etf)
        industries = taxonomy[etf]

        logger.info(f"  {etf} ({sector_name}): {len(industries)} industries")

        # Calculate industry-level rotation using weekly data
        industry_rotations = calc_industry_rotation(
            weekly_data, industries, window=1,  # 1 week bars
        )

        # Also compute using daily data for stock detail
        industry_rotations_daily = calc_industry_rotation(
            daily_data, industries, window=args.rotation_window,
        )

        # Rank industries
        ranking = rank_industries(industry_rotations_daily, etf)

        # Stock detail for each industry
        stock_details = {}
        for ind_name, tickers in industries.items():
            clean_name = ind_name.lstrip("*")
            sd = get_stock_detail(daily_data, tickers, window=args.rotation_window)
            if not sd.empty:
                stock_details[clean_name] = sd

        sector_results[etf] = {
            "name": sector_name,
            "ranking": ranking,
            "time_series": {k: v for k, v in industry_rotations.items()},
            "stock_detail": stock_details,
        }

        # Collect for anomaly detection
        for k, v in industry_rotations.items():
            all_industry_rotations[k] = v

        if not ranking.empty:
            top = ranking.iloc[0]
            bot = ranking.iloc[-1]
            logger.info(f"    Top: {top['industry']} ({top['rotation_rel']:.3f})")
            logger.info(f"    Bottom: {bot['industry']} ({bot['rotation_rel']:.3f})")

    # --- Detect anomalies ---
    logger.info("Step 4/4: Detecting rotation anomalies...")
    anomalies = calc_rotation_anomalies(
        all_industry_rotations,
        zscore_window=args.zscore_window,
        threshold=args.threshold,
    )

    if not anomalies.empty:
        inflows = anomalies[anomalies["direction"] == "inflow_surge"]
        outflows = anomalies[anomalies["direction"] == "outflow_surge"]
        logger.info(f"  {len(anomalies)} anomalies found:")
        logger.info(f"    Inflow surges: {len(inflows)}")
        logger.info(f"    Outflow surges: {len(outflows)}")
    else:
        logger.info("  No anomalies found at threshold {args.threshold}")

    # --- Generate report ---
    logger.info("Generating HTML report...")
    config_summary = {
        "lookback_weeks": args.lookback,
        "rotation_window": args.rotation_window,
        "zscore_threshold": args.threshold,
        "n_sectors": len(sector_etfs),
        "n_tickers": len(all_tickers),
    }

    report_path = generate_report(
        sector_data=sector_results,
        anomalies=anomalies,
        config_summary=config_summary,
        output_path=args.output,
    )

    logger.info(f"Report saved to: {report_path}")
    logger.info("Done.")


if __name__ == "__main__":
    main()
