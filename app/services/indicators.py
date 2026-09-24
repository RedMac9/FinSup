"""
Custom indicator plugin registry for the open-positions chart.

Each indicator is a plain Python function that takes a tidy OHLC DataFrame and
returns a list of "series" dicts that the front-end (TradingView Lightweight
Charts) knows how to draw. Adding a new indicator is just: write a function,
add one entry to INDICATORS. No chart-code changes required.

Expected OHLC DataFrame (ascending by date):
    columns -> Date (datetime64), Open, High, Low, Close, optional Volume

Series dict contract (one indicator may return several series):
    {
        "title": str,                       # legend label
        "pane":  "main" | "separate",       # main price scale, or its own sub-pane
        "type":  "line" | "histogram" | "markers" | "band",
        "color": "#rrggbb",
        "data":  [...],                      # see below per type
        "indicator": str,                   # registry name - set by compute_indicators()
    }

    line / histogram data -> [{"time": "YYYY-MM-DD", "value": float,
                               "color": str (optional, histogram only)}, ...]
    markers data          -> [{"time": "YYYY-MM-DD", "position": "aboveBar"|"belowBar",
                               "color": str, "shape": "arrowUp"|"arrowDown"|"circle",
                               "text": str}, ...]
    band data             -> [{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD",
                               "top": float, "bottom": float, "color": str,
                               "label": str, "detail": str}, ...]
                             (+ series-level "opacity": float) - shaded price
                             rectangles, e.g. DiNapoli zones.

Markers are attached to the main candlestick series by the front-end. Every
"separate" series of one indicator shares one sub-pane.
"""

import pandas as pd

from services.dinapoli_overlay import (
    dinapoli_breakouts, dinapoli_dma, dinapoli_failures, dinapoli_levels,
    dinapoli_macd_predictor, dinapoli_overbought_oversold, dinapoli_setups,
    dinapoli_zones, dinapoli_zones_all,
)

# Volume spike = volume at least this many times its VOLUME_AVG_WINDOW-day
# average ("na większych obrotach" in the strategy document).
VOLUME_AVG_WINDOW = 20
VOLUME_SPIKE_MULT = 1.8


def resample_ohlc(df, rule="W"):
    """Tidy daily (Date, Open, High, Low, Close[, Volume]) -> the same shape on
    a higher interval. Each candle is dated by its LAST actual session (not the
    period-end calendar date), so it lines up with daily dates and never lands
    in the future for the unfinished current week."""
    if df is None or df.empty:
        return df
    agg = {"Date": "last", "Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df.columns:
        agg["Volume"] = "sum"
    out = (df.set_index(pd.DatetimeIndex(pd.to_datetime(df["Date"])), drop=False)
             .resample(rule).agg(agg))
    return out.dropna(subset=["Close"]).reset_index(drop=True)


def _time_str(series_index) -> list:
    """Convert a date Series/Index into 'YYYY-MM-DD' strings."""
    return pd.DatetimeIndex(pd.to_datetime(series_index)).strftime("%Y-%m-%d").tolist()


def _line_series(df, values, title, color, pane="main", kind="line"):
    """Build a line/histogram series dict, dropping NaN points."""
    s = pd.Series(values).reset_index(drop=True)
    times = _time_str(df["Date"])
    data = [
        {"time": t, "value": float(v)}
        for t, v in zip(times, s)
        if pd.notna(v)
    ]
    return {"title": title, "pane": pane, "type": kind, "color": color, "data": data}


# --- Indicator functions ----------------------------------------------------
# Formulas mirror app/services/market_metrics.py and app/output/graph.py.


def _sma(df, window, color):
    sma = df["Close"].rolling(window=window).mean()
    return [_line_series(df, sma, f"SMA{window}", color)]


def _ema(df, span, color):
    ema = df["Close"].ewm(span=span, adjust=False).mean()
    return [_line_series(df, ema, f"EMA{span}", color)]


def sma10(df):
    return _sma(df, 10, "#f59e0b")


def sma20(df):
    return _sma(df, 20, "#3b82f6")


def sma50(df):
    return _sma(df, 50, "#8b5cf6")


def ema10(df):
    return _ema(df, 10, "#10b981")


def ema20(df):
    return _ema(df, 20, "#ec4899")


def ema32(df):
    return _ema(df, 32, "#ef4444")


def sma100(df):
    return _sma(df, 100, "#15803d")


def sma200(df):
    return _sma(df, 200, "#1d4ed8")


def volume(df):
    """Volume bars in their own pane, green on up-candles and red on down."""
    if "Volume" not in df.columns:
        return []
    times = _time_str(df["Date"])
    data = [
        {"time": t, "value": float(v),
         "color": "#86efac" if c >= o else "#fca5a5"}
        for t, v, o, c in zip(times, df["Volume"], df["Open"], df["Close"])
        if pd.notna(v)
    ]
    avg = df["Volume"].rolling(VOLUME_AVG_WINDOW).mean()
    return [
        {"title": "Volume", "pane": "separate", "type": "histogram",
         "color": "#94a3b8", "data": data},
        _line_series(df, avg, f"Vol avg{VOLUME_AVG_WINDOW}", "#475569", pane="separate"),
    ]


def volume_spikes(df):
    """Markers on bars whose volume is >= VOLUME_SPIKE_MULT x its average."""
    if "Volume" not in df.columns:
        return []
    ratio = df["Volume"] / df["Volume"].rolling(VOLUME_AVG_WINDOW).mean()
    times = _time_str(df["Date"])
    markers = []
    for t, r, o, c in zip(times, ratio, df["Open"], df["Close"]):
        if pd.notna(r) and r >= VOLUME_SPIKE_MULT:
            up = c >= o
            markers.append({"time": t, "position": "belowBar" if up else "aboveBar",
                            "color": "#0369a1", "shape": "circle",
                            "text": f"Vol×{r:.1f}"})
    return [{"title": "Volume spikes", "pane": "main", "type": "markers",
             "color": "#0369a1", "data": markers}]


def gaps(df):
    """Luka hossy (low above previous high) / luka bessy (high below previous low)."""
    prev_high, prev_low = df["High"].shift(1), df["Low"].shift(1)
    times = _time_str(df["Date"])
    markers = []
    for t, lo, hi, ph, pl in zip(times, df["Low"], df["High"], prev_high, prev_low):
        if pd.notna(ph) and lo > ph:
            markers.append({"time": t, "position": "belowBar", "color": "#16a34a",
                            "shape": "circle", "text": "luka hossy"})
        elif pd.notna(pl) and hi < pl:
            markers.append({"time": t, "position": "aboveBar", "color": "#dc2626",
                            "shape": "circle", "text": "luka bessy"})
    return [{"title": "Gaps", "pane": "main", "type": "markers",
             "color": "#16a34a", "data": markers}]


def volume_ratio(df):
    """Last bar's volume / its VOLUME_AVG_WINDOW-day average (None if unknown).
    Screener helper, not a chart layer."""
    if df is None or "Volume" not in df.columns or len(df) < VOLUME_AVG_WINDOW:
        return None
    avg = df["Volume"].rolling(VOLUME_AVG_WINDOW).mean().iloc[-1]
    last = df["Volume"].iloc[-1]
    if pd.isna(avg) or not avg or pd.isna(last):
        return None
    return float(last / avg)


def ath30_line(df):
    """30-day rolling all-time-high overlaid on price."""
    ath30 = df["Close"].rolling(window=30, min_periods=1).max()
    return [_line_series(df, ath30, "ATH30", "#64748b")]


def pct_from_ath30(df):
    """% distance from the 30-day rolling high, drawn in its own pane.

    Formula from app/output/graph.py: (Close - ath30) / ath30 * 100.
    """
    ath30 = df["Close"].rolling(window=30, min_periods=1).max()
    pct = (df["Close"] - ath30) / ath30.replace(0, pd.NA) * 100
    return [_line_series(df, pct, "% from ATH30", "#0ea5e9", pane="separate")]


def ema32_cross_markers(df):
    """Markers where Close crosses the EMA32 (the DaysCloseAboveEMA32 signal)."""
    ema = df["Close"].ewm(span=32, adjust=False).mean()
    above = df["Close"] > ema
    cross = above.ne(above.shift(1))
    times = _time_str(df["Date"])
    markers = []
    for i, (t, is_cross, is_above) in enumerate(zip(times, cross, above)):
        if i == 0 or not is_cross:
            continue
        if is_above:
            markers.append({"time": t, "position": "belowBar",
                            "color": "#10b981", "shape": "arrowUp", "text": "↑EMA32"})
        else:
            markers.append({"time": t, "position": "aboveBar",
                            "color": "#ef4444", "shape": "arrowDown", "text": "↓EMA32"})
    return [{"title": "EMA32 cross", "pane": "main", "type": "markers",
             "color": "#10b981", "data": markers}]


# --- Registry ---------------------------------------------------------------
# name -> {func, default_on}. Order here is the order shown in the UI.

INDICATORS = {
    "SMA10": {"func": sma10, "default_on": False},
    "SMA20": {"func": sma20, "default_on": True},
    "SMA50": {"func": sma50, "default_on": False},
    "SMA100": {"func": sma100, "default_on": False},
    "SMA200": {"func": sma200, "default_on": False},
    "EMA10": {"func": ema10, "default_on": False},
    "EMA20": {"func": ema20, "default_on": False},
    "EMA32": {"func": ema32, "default_on": True},
    "ATH30": {"func": ath30_line, "default_on": False},
    "% from ATH30": {"func": pct_from_ath30, "default_on": False},
    "EMA32 cross": {"func": ema32_cross_markers, "default_on": False},
    "Volume": {"func": volume, "default_on": False},
    "Volume spikes": {"func": volume_spikes, "default_on": False},
    "Gaps": {"func": gaps, "default_on": False},
    # DiNapoli confluence/levels system - logic lives in services/dinapoli/,
    # all tuning (fib ratios, tolerances, colors, scan window) in
    # services/dinapoli_settings.py. See services/dinapoli_overlay.py for the
    # translation into these series dicts.
    "DiNapoli Zones": {"func": dinapoli_zones, "default_on": False},
    "DiNapoli Zones (all)": {"func": dinapoli_zones_all, "default_on": False},
    "DiNapoli Levels": {"func": dinapoli_levels, "default_on": False},
    "DiNapoli DMA": {"func": dinapoli_dma, "default_on": False},
    "DiNapoli MacdPred": {"func": dinapoli_macd_predictor, "default_on": False},
    "DiNapoli OB/OS": {"func": dinapoli_overbought_oversold, "default_on": False},
    "DiNapoli Setups": {"func": dinapoli_setups, "default_on": False},
    "DiNapoli Failures": {"func": dinapoli_failures, "default_on": False},
    "DiNapoli Breakouts": {"func": dinapoli_breakouts, "default_on": False},
}

# Default layer set for DiNapoli-style single-ticker views (the open-positions
# chart): what the strategy document's charts show - MA50/100/200, DMA 3x3 &
# 25x5, the nearest zones, setups, volume. The screener's short-term averages
# (SMA10/20, EMA10/20/32, ATH30) stay available but start off there.
DINAPOLI_DEFAULTS = [
    "SMA50", "SMA100", "SMA200", "DiNapoli DMA", "DiNapoli Zones",
    "DiNapoli Setups", "Volume",
]


def compute_indicators(df, selected_names):
    """Run the selected indicators and return a flat list of series dicts.

    Silently skips indicators that raise (e.g. too few data points) so one bad
    indicator never blanks the whole chart.
    """
    out = []
    for name in selected_names:
        spec = INDICATORS.get(name)
        if not spec:
            continue
        try:
            for s in spec["func"](df):
                s["indicator"] = name
                out.append(s)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Indicator '{name}' failed: {exc}")
    return out
