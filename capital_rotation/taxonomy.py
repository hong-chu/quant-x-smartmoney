"""
IBD-style Industry Group Taxonomy.

Maps sector ETFs → industry groups → representative tickers.
Based on the IBD 197 Industry Groups classification with custom additions
for emerging themes (AI infrastructure, quantum computing, space tech, etc.).

Users can extend this by providing a custom YAML/JSON taxonomy file.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class IndustryGroup:
    """A single industry group within a sector."""
    name: str
    sector_etf: str
    tickers: list[str] = field(default_factory=list)
    is_custom: bool = False  # True if user-added or AI-era addition
    description: str = ""


# ---------------------------------------------------------------------------
# Sector ETF → Industry Group mapping
# ---------------------------------------------------------------------------
# Format: { "ETF": { "Industry Name": [tickers] } }
# Custom/emerging groups are prefixed with ** in CoreEdge style
#
# Note: Ticker lists are representative, not exhaustive.
# The tool will dynamically expand by fetching all stocks in each industry
# from the data provider.
# ---------------------------------------------------------------------------

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financial",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLC": "Communication Services",
}

# Reverse mapping
ETF_BY_SECTOR = {v: k for k, v in SECTOR_ETFS.items()}


TAXONOMY: dict[str, dict[str, list[str]]] = {
    # ---- Technology (XLK) ----
    "XLK": {
        "Computer-Data Storage": [
            "MU", "SNDK", "STX", "WDC", "NTAP", "PSTG", "SMCI",
        ],
        "Computer-Hardware/Periph": [
            "AAPL", "HPQ", "HPE", "DELL", "LOGI", "CRSR",
        ],
        "Computer-Networking": [
            "CSCO", "ANET", "JNPR", "NTGR", "CIEN", "INFN",
        ],
        "Computer-Tech Services": [
            "ACN", "IBM", "CTSH", "EPAM", "GLOB", "DXC", "LDOS",
        ],
        "Computer Sftwr-Enterprise": [
            "CRM", "NOW", "WDAY", "INTU", "TEAM", "HUBS", "DDOG",
        ],
        "Computer Sftwr-Security": [
            "CRWD", "PANW", "FTNT", "ZS", "S", "CYBR", "QLYS",
        ],
        "Computer Sftwr-Design": [
            "ADBE", "ANSS", "CDNS", "SNPS", "PTC", "ADSK",
        ],
        "Computer Sftwr-Database": [
            "ORCL", "MDB", "SNOW", "ESTC", "CLSK",
        ],
        "Computer Sftwr-Edu/Media": [
            "MSFT", "GOOG", "GOOGL",
        ],
        "Comp Sftwr-Spec Enterprs": [
            "PLTR", "VEEV", "PAYC", "PCTY", "TYL",
        ],
        "Computer-Integrated Syst/POS/ATM": [
            "NCR", "PAX", "TOST", "SQ",
        ],
        "Elec-Semiconductor Mfg": [
            "INTC", "TSM", "GFS", "UMC", "AMKR",
        ],
        "Elec-Semiconductor Fabless": [
            "NVDA", "AMD", "QCOM", "AVGO", "MRVL", "ARM",
            "SIMO", "SYNA", "AMBA", "CGNX",
        ],
        "Elec-Semiconductor Equip": [
            "AMAT", "LRCX", "KLAC", "ASML", "TER", "ONTO",
        ],
        "Elec-Contract Mfg": [
            "FLEX", "JBL", "CLS", "SANM",
        ],
        "Elec-Scientific/Measrng": [
            "KEYS", "TDY", "FTV", "GRMN", "COHR",
        ],
        "Electronic-Parts": [
            "APH", "TEL", "GLW", "AMPH", "CUI",
        ],
        "Elec-Misc Products": [
            "ENPH", "SEDG", "ITRI",
        ],
        "Internet-Network Sltns": [
            "NET", "AKAM", "FSLY", "CDW",
        ],
        "Telecom-Fiber Optics": [
            "LITE", "II", "VIAV", "COMM",
        ],
        "Telecom-Infrastructure": [
            "AMT", "CCI", "SBAC", "UNIT",
        ],
        "Telecom-Cable/Satl Eqp": [
            "GRMN", "GILT",
        ],
        "Telecom-Consumer Prods": [
            "SONO", "HEAR",
        ],
        "Wholesale-Electronics": [
            "ARW", "AVT", "SCSC",
        ],
        "Consumer Prod-Electronic": [
            "ROKU", "PTON",
        ],
        # Custom / Emerging groups
        "**Computer-AI Infra": [
            "NVDA", "AMD", "SMCI", "VRT", "ANET", "DELL",
            "MSFT", "AMZN", "GOOG", "META",
        ],
        "**Computer-Quantum Computing": [
            "IONQ", "RGTI", "QBTS", "QUBT", "ARQQ",
        ],
        "**AeroSpace-New Space Tech": [
            "RKLB", "ASTS", "RDW", "LUNR", "BKSY",
        ],
        "**Energy-Solar": [
            "ENPH", "SEDG", "FSLR", "RUN", "NOVA", "ARRY",
        ],
    },

    # ---- Financials (XLF) ----
    "XLF": {
        "Banks-Money Center": [
            "JPM", "BAC", "WFC", "C", "USB",
        ],
        "Banks-Regional": [
            "PNC", "TFC", "FITB", "HBAN", "KEY", "CFG", "RF",
        ],
        "Banks-Investment/Brokerage": [
            "GS", "MS", "SCHW", "RJF",
        ],
        "Finance-Credit Card/Payment": [
            "V", "MA", "AXP", "DFS", "PYPL", "SQ",
        ],
        "Finance-Insurance/Brokerage": [
            "BRK-B", "AIG", "MET", "PRU", "ALL", "TRV",
        ],
        "Finance-Property/Casualty Ins": [
            "PGR", "CB", "CINF", "HIG",
        ],
        "Finance-Life Insurance": [
            "AFL", "GL", "LNC", "VOYA",
        ],
        "Finance-Asset Management": [
            "BLK", "BX", "KKR", "APO", "ARES", "OWL",
        ],
        "Finance-REIT/Equity Trust": [
            "SPG", "PLD", "O", "VICI", "WPC",
        ],
        "Finance-Exchange/Clearing": [
            "CME", "ICE", "NDAQ", "CBOE",
        ],
        "Finance-Fintech/Digital": [
            "FIS", "FISV", "GPN", "AFRM", "UPST",
        ],
        "Finance-Mortgage/Related": [
            "RKT", "UWMC", "PFSI", "COOP",
        ],
    },

    # ---- Energy (XLE) ----
    "XLE": {
        "Oil&Gas-Integrated": [
            "XOM", "CVX", "SHEL", "TTE", "BP",
        ],
        "Oil&Gas-Exploration/Prod": [
            "COP", "EOG", "PXD", "DVN", "FANG", "OXY",
        ],
        "Oil&Gas-Field Services": [
            "SLB", "HAL", "BKR", "FTI", "NOV",
        ],
        "Oil&Gas-Refining": [
            "MPC", "PSX", "VLO", "DINO",
        ],
        "Oil&Gas-Pipeline/MLP": [
            "WMB", "KMI", "OKE", "TRGP", "ET", "EPD",
        ],
        "Oil&Gas-Drilling": [
            "RIG", "HP", "NBR",
        ],
        "Energy-Alternative/Renewable": [
            "NEE", "PLUG", "BE", "FCEL",
        ],
    },

    # ---- Healthcare (XLV) ----
    "XLV": {
        "Drug-Major Pharma": [
            "JNJ", "LLY", "MRK", "PFE", "ABBV", "BMY", "NVS",
        ],
        "Drug-Biotech": [
            "AMGN", "GILD", "VRTX", "REGN", "MRNA", "BIIB",
        ],
        "Drug-Generic/Specialty": [
            "TEVA", "MYL", "ZTS",
        ],
        "Medical-Systems/Equipment": [
            "ABT", "MDT", "SYK", "BSX", "EW", "ISRG",
        ],
        "Medical-Diagnostics": [
            "TMO", "DHR", "A", "BIO", "ILMN",
        ],
        "Medical-Products": [
            "BDX", "BAX", "ZBH", "HOLX",
        ],
        "Medical-HMO/PPO": [
            "UNH", "ELV", "CI", "CNC", "HUM",
        ],
        "Medical-Services": [
            "HCA", "UHS", "THC", "DVA",
        ],
        "Medical-Dental/Optical": [
            "ALGN", "XRAY", "COO",
        ],
        "**Drug-GLP1/Obesity": [
            "LLY", "NVO", "AMGN", "VKTX",
        ],
    },

    # ---- Consumer Discretionary (XLY) ----
    "XLY": {
        "Retail-Internet/E-Commerce": [
            "AMZN", "BABA", "MELI", "ETSY", "W", "CHWY",
        ],
        "Retail-Restaurants": [
            "MCD", "SBUX", "CMG", "YUM", "DPZ", "QSR",
        ],
        "Retail-Home Furnishing": [
            "HD", "LOW", "WSM", "RH", "BBBY",
        ],
        "Retail-Apparel/Shoes": [
            "NKE", "TJX", "ROST", "GPS", "ANF", "AEO",
        ],
        "Retail-Discount/Variety": [
            "WMT", "COST", "TGT", "DG", "DLTR",
        ],
        "Auto/Truck-Original Equip": [
            "TSLA", "GM", "F", "RIVN", "LCID",
        ],
        "Auto/Truck-Parts/Equip": [
            "APTV", "BWA", "ALV", "LEA",
        ],
        "Leisure-Hotels/Motels": [
            "MAR", "HLT", "H", "WH", "ABNB",
        ],
        "Leisure-Travel/Booking": [
            "BKNG", "EXPE", "TRIP", "TCOM",
        ],
        "Leisure-Gaming/Equipment": [
            "DKNG", "FLUT", "MGM", "CZR", "WYNN",
        ],
        "Building-Residential/Comml": [
            "DHI", "LEN", "NVR", "PHM", "TOL",
        ],
    },

    # ---- Consumer Staples (XLP) ----
    "XLP": {
        "Food-Packaged/Proc": [
            "PG", "KO", "PEP", "MDLZ", "GIS", "KHC", "HSY",
        ],
        "Food-Dairy Products": [
            "CAG", "SJM", "CPB",
        ],
        "Household/Personal Care": [
            "CL", "KMB", "CHD", "CLX", "EL",
        ],
        "Tobacco": [
            "PM", "MO", "BTI",
        ],
        "Beverages-Alcohol": [
            "STZ", "BF-B", "DEO", "SAM",
        ],
        "Beverages-Non-Alcohol": [
            "KDP", "MNST", "CELH",
        ],
        "Retail-Supermarket/Mini-Mart": [
            "KR", "ACI", "SFM",
        ],
    },

    # ---- Industrials (XLI) ----
    "XLI": {
        "Aerospace/Defense": [
            "BA", "LMT", "RTX", "GD", "NOC", "LHX", "HII",
        ],
        "Machinery-General Industrial": [
            "CAT", "DE", "EMR", "ROK", "DOV",
        ],
        "Transportation-Rail": [
            "UNP", "CSX", "NSC", "CP",
        ],
        "Transportation-Airline": [
            "DAL", "UAL", "LUV", "AAL", "JBLU",
        ],
        "Transportation-Truck/Ship": [
            "FDX", "UPS", "XPO", "ODFL", "SAIA",
        ],
        "Electrical-Power/Equipment": [
            "ETN", "EMR", "PH", "AME", "GEV", "NVT", "POWL",
        ],
        "Pollution Control": [
            "WM", "RSG", "WCN", "CLH",
        ],
        "Staffing/HR Services": [
            "ADP", "PAYX", "RHI", "MAN",
        ],
        "Conglomerate/Diversified": [
            "GE", "HON", "MMM", "ITW",
        ],
        "**Defense-Drones/Unmanned": [
            "AVAV", "KTOS", "RKLB",
        ],
        "**Electrification-Grid Infra": [
            "GEV", "NVT", "POWL", "ETN", "VRT",
        ],
    },

    # ---- Materials (XLB) ----
    "XLB": {
        "Chemical-Diversified": [
            "LIN", "APD", "DD", "DOW", "ECL",
        ],
        "Chemical-Specialty": [
            "SHW", "PPG", "IFF", "CE", "EMN",
        ],
        "Chemical-Agriculture": [
            "CTVA", "CF", "MOS", "FMC", "NTR",
        ],
        "Mining-Gold/Silver": [
            "NEM", "GOLD", "GFI", "AEM", "KGC",
        ],
        "Mining-Copper/Base Metals": [
            "FCX", "SCCO", "TECK",
        ],
        "Steel/Iron": [
            "NUE", "STLD", "CLF", "X",
        ],
        "Building-Cement/Aggregate": [
            "VMC", "MLM", "EXP",
        ],
        "Paper/Forest Products": [
            "IP", "PKG", "WRK",
        ],
        "Mining-Lithium/Battery Metals": [
            "ALB", "SQM", "LTHM",
        ],
    },

    # ---- Real Estate (XLRE) ----
    "XLRE": {
        "REIT-Data Center": [
            "EQIX", "DLR", "AMT",
        ],
        "REIT-Retail": [
            "SPG", "O", "REG", "KIM", "FRT",
        ],
        "REIT-Industrial/Logistics": [
            "PLD", "REXR", "FR",
        ],
        "REIT-Residential": [
            "AVB", "EQR", "MAA", "UDR", "ESS",
        ],
        "REIT-Healthcare": [
            "WELL", "VTR", "DOC", "OHI",
        ],
        "REIT-Office": [
            "BXP", "VNO", "SLG",
        ],
        "REIT-Specialty": [
            "VICI", "CCI", "PSA", "EXR", "CUBE",
        ],
    },

    # ---- Utilities (XLU) ----
    "XLU": {
        "Utilities-Electric": [
            "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE",
        ],
        "Utilities-Gas Distribution": [
            "NI", "ATO", "SWX",
        ],
        "Utilities-Water": [
            "AWK", "WTR", "SJW",
        ],
        "Utilities-Diversified": [
            "ES", "ED", "WEC", "DTE", "CMS", "XEL", "PPL",
        ],
        "**Utilities-Nuclear/SMR": [
            "CEG", "VST", "TLN", "SMR", "OKLO",
        ],
    },

    # ---- Communication Services (XLC) ----
    "XLC": {
        "Internet-Content": [
            "META", "GOOGL", "SNAP", "PINS", "RDDT",
        ],
        "Media-Streaming/Entertainment": [
            "NFLX", "DIS", "WBD", "PARA",
        ],
        "Media-Periodicals/Publishing": [
            "NWSA", "NYT",
        ],
        "Telecom-Wireless Services": [
            "T", "VZ", "TMUS",
        ],
        "Telecom-Cable/CATV": [
            "CMCSA", "CHTR",
        ],
        "Computer-Gaming": [
            "EA", "TTWO", "RBLX",
        ],
        "Internet-Social/Messaging": [
            "SPOT", "MTCH", "BMBL",
        ],
        "Advertising-Digital": [
            "TTD", "MGNI", "DV", "OMC",
        ],
    },
}


def get_all_industry_groups() -> list[IndustryGroup]:
    """Return a flat list of all industry groups across all sectors."""
    groups = []
    for etf, industries in TAXONOMY.items():
        for name, tickers in industries.items():
            is_custom = name.startswith("**")
            clean_name = name.lstrip("*")
            groups.append(IndustryGroup(
                name=clean_name,
                sector_etf=etf,
                tickers=tickers,
                is_custom=is_custom,
            ))
    return groups


def get_sector_groups(etf: str) -> dict[str, list[str]]:
    """Return industry groups for a specific sector ETF."""
    return TAXONOMY.get(etf, {})


def get_all_tickers() -> set[str]:
    """Return all unique tickers across all industry groups."""
    tickers = set()
    for industries in TAXONOMY.values():
        for ticker_list in industries.values():
            tickers.update(ticker_list)
    return tickers


def get_ticker_industry_map() -> dict[str, list[str]]:
    """Map each ticker to its industry group(s). A ticker can belong to multiple groups."""
    mapping: dict[str, list[str]] = {}
    for industries in TAXONOMY.values():
        for name, tickers in industries.items():
            clean_name = name.lstrip("*")
            for t in tickers:
                mapping.setdefault(t, []).append(clean_name)
    return mapping


def load_custom_taxonomy(path: str) -> dict[str, dict[str, list[str]]]:
    """
    Load a custom taxonomy from a JSON file and merge with the base taxonomy.

    Expected format:
    {
        "XLK": {
            "**My-Custom-Group": ["TICK1", "TICK2"]
        }
    }
    """
    p = Path(path)
    if not p.exists():
        logger.warning(f"Custom taxonomy file not found: {path}")
        return TAXONOMY

    with open(p) as f:
        custom = json.load(f)

    merged = {k: dict(v) for k, v in TAXONOMY.items()}
    for etf, industries in custom.items():
        if etf not in merged:
            merged[etf] = {}
        for name, tickers in industries.items():
            merged[etf][name] = tickers
            logger.info(f"  Added custom group: {etf}/{name} ({len(tickers)} tickers)")

    return merged
