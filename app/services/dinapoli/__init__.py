"""System poziomów DiNapoliego - Zgodność, Zgęszczenie, zasięgi, setupy.

Szybki start:

    import pandas as pd
    from services.dinapoli import Analyzer

    df = pd.read_csv("kgh.csv", parse_dates=["date"], index_col="date")
    a = Analyzer(df, symbol="KGH")

    print(a.snapshot().report())     # stan na dziś
    sig = a.signal()                 # sygnał na dziś, jeśli jest
    signals = a.scan(start=300)      # przejście po historii
"""

from .config import (Config, ConfluenceConfig, DEFAULT, IndicatorConfig,
                     LevelConfig, RiskConfig, SetupConfig, SwingConfig,
                     TrendConfig)
from .confluence import Zone, find_zones, nearest_resistance, nearest_support
from .indicators import (atr, dma, macd_predictor, oscillator_predictor,
                         detrended_oscillator)
from .levels import Level, all_levels, expansion_levels, retracement_levels
from .setups import Setup
from .swings import Leg, Swing, detect_swings
from .system import Analyzer, Signal, Snapshot
from .trend import trend_state, trend_alignment, resample

__version__ = "0.1.0"

__all__ = [
    "Analyzer", "Signal", "Snapshot", "Config", "DEFAULT",
    "Zone", "Level", "Swing", "Leg", "Setup",
    "find_zones", "nearest_support", "nearest_resistance",
    "all_levels", "retracement_levels", "expansion_levels",
    "detect_swings", "trend_state", "trend_alignment", "resample",
    "atr", "dma", "macd_predictor", "oscillator_predictor",
    "detrended_oscillator",
]
