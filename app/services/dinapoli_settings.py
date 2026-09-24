"""Single point of configuration for the DiNapoli overlay indicator.

Everything that controls how the DiNapoli confluence/levels indicator looks
and behaves on the open-positions chart (app/output/positions_chart.py, via
the plugin registry in app/services/indicators.py) lives in this one file.
`dinapoli_overlay.py` and `indicators.py` must not hardcode a threshold or
color for it - they import from here instead.

To retune the indicator:
    - fib ratios, confluence tolerance, swing detection, setup/risk rules
      -> edit the `Config` fields below (app/services/dinapoli/config.py holds
         the package defaults; DINAPOLI_CONFIG is what actually gets used)
    - which zones/levels are drawn, how many, how far back setups are scanned,
      colors -> edit the OVERLAY_* constants below
"""

from services.dinapoli.config import Config

# The Config dataclass tree (app/services/dinapoli/config.py) already
# centralizes every tunable parameter of the indicator engine itself. Override
# any field here if FinSup's data (equities/ETFs, ~6 months of daily bars)
# should behave differently from the package defaults.
DINAPOLI_CONFIG = Config()

# --- Display / wiring for the positions_chart plugin ----------------------

# Below this many daily bars, swings/levels are too noisy to bother drawing.
OVERLAY_MIN_BARS = 60

# Zones weaker than this (Zone.strength, 0-10 scale) are not drawn - keeps
# the chart readable instead of shading every minor coincidence.
OVERLAY_MIN_ZONE_STRENGTH = 2.0
# "DiNapoli Zones (all)": up to this many strongest zones.
OVERLAY_MAX_ZONES = 8
# "DiNapoli Zones": only the N nearest supports below and N nearest
# resistances above the last close - how the source document's charts look
# (3-5 bands, not every cluster).
OVERLAY_NEAREST_ZONES = 2
# Band fill opacity (0-1) for zone rectangles.
OVERLAY_ZONE_OPACITY = 0.18

# Standalone Fibonacci level lines (as opposed to clustered zones) are drawn
# only within the confluence engine's own "how far to look" band around the
# last close (DINAPOLI_CONFIG.confluence.lookahead_pct), closest first, capped
# here - otherwise every retracement/expansion from every swing on every
# timeframe gets drawn (100+ lines) and the chart becomes unreadable.
OVERLAY_MAX_LEVELS = 20

# Setup/signal markers are found by re-scanning history bar by bar (each bar
# re-runs swing detection + zone clustering), which is by far the most
# expensive layer - roughly 10ms per bar scanned, vs. <50ms total for every
# other layer combined. Raise this if you want deeper marker history and can
# afford ~1s/ticker per +100 bars; lower it if the chart feels sluggish.
OVERLAY_SETUPS_SCAN_BARS = 40

# "Niespełnienie" (failed setup): a long setup fails when, within this many
# bars after it fired, a close lands below that setup bar's low (short:
# above its high). Uses the same scan window as the setup markers.
OVERLAY_FAILURE_BARS = 5

# Breakout events (close crossing DMA 25x5 / MacdPred / a current zone) are
# marked over this many most recent bars. Cheap - no per-bar re-scan.
OVERLAY_EVENTS_SCAN_BARS = 60

OVERLAY_COLORS = {
    "zone_support": "#16a34a",
    "zone_resistance": "#dc2626",
    "zone_expansion": "#db2777",     # "kumulacja ekspansji" - pink like the source charts
    "breakout_up": "#0d9488",
    "breakout_down": "#b91c1c",
    "failure": "#7c2d12",
    "level_retracement": "#94a3b8",
    "level_expansion": "#2563eb",
    "dma_fast": "#c0392b",
    "dma_slow": "#16a34a",
    "macd_pred": "#8e44ad",
    "osc_overbought": "#dc2626",
    "osc_oversold": "#16a34a",
    "setup_long": "#16a34a",
    "setup_short": "#dc2626",
}
