"""Configuration for the capital rotation pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RotationConfig:
    """Configuration for a single pipeline run."""

    # Sectors to scan (ETF symbols, e.g. ["XLK", "XLF"])
    # None = scan all sectors
    sectors: Optional[list[str]] = None

    # Data parameters
    lookback_weeks: int = 20        # weeks of history for rotation chart
    provider: str = "yfinance"      # data provider
    cache_dir: Optional[str] = ".cache"

    # Rotation calculation
    rotation_window: int = 5        # trading days for rotation metric (1 week)

    # Anomaly detection
    zscore_window: int = 12         # weeks for Z-score baseline
    zscore_threshold: float = 2.0   # |Z| above this = anomaly

    # Custom taxonomy
    custom_taxonomy: Optional[str] = None  # path to custom JSON taxonomy

    # Output
    output_path: str = "capital_rotation_report.html"
