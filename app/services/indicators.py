"""
Custom indicator plugin registry for the open-positions chart.

Each indicator is a plain Python function that takes a tidy OHLC DataFrame and
returns a list of "series" dicts that the front-end (TradingView Lightweight
Charts) knows how to draw. Adding a new indicator is just: write a function,
add one entry to INDICATORS. No chart-code changes required.

Expected OHLC DataFrame (ascending by date):
    columns -> Date (datetime64), Open, High, Low, Close

Series dict contract (one indicator may return several series):
    {
        "title": str,                       # legend label
        "pane":  "main" | "separate",       # main price scale, or its own
        "type":  "line" | "histogram" | "markers",
        "color": "#rrggbb",
        "data":  [...]                       # see below per type
    }

    line / histogram data -> [{"time": "YYYY-MM-DD", "value": float}, ...]
    markers data          -> [{"time": "YYYY-MM-DD", "position": "aboveBar"|"belowBar",
                               "color": str, "shape": "arrowUp"|"arrowDown"|"circle",
                               "text": str}, ...]

Markers are attached to the main candlestick series by the front-end.
"""

import pandas as pd


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
    "EMA10": {"func": ema10, "default_on": False},
    "EMA20": {"func": ema20, "default_on": False},
    "EMA32": {"func": ema32, "default_on": True},
    "ATH30": {"func": ath30_line, "default_on": False},
    "% from ATH30": {"func": pct_from_ath30, "default_on": False},
    "EMA32 cross": {"func": ema32_cross_markers, "default_on": False},
}


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
            out.extend(spec["func"](df))
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Indicator '{name}' failed: {exc}")
    return out
