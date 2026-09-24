"""Adapter: DiNapoli Analyzer output -> the services/indicators.py series contract.

Pure translation layer between app/services/dinapoli/ (the vendored
confluence/levels engine) and the "line / histogram / markers / band" series
dicts that the chart front-ends (positions_chart.py -> tv_chart.js, and
graph.py -> plotly) know how to draw.

No threshold, color or scan-window lives in this file - everything tunable
comes from dinapoli_settings.py. This file only reshapes data.
"""

from bisect import bisect_right

import pandas as pd

from services.dinapoli.swings import detect_swings
from services.dinapoli.system import Analyzer
from services.dinapoli.trend import SIDE, resample, trend_alignment, trend_state
from services.dinapoli_settings import (
    DINAPOLI_CONFIG, OVERLAY_COLORS, OVERLAY_EVENTS_SCAN_BARS, OVERLAY_FAILURE_BARS,
    OVERLAY_MAX_LEVELS, OVERLAY_MAX_ZONES, OVERLAY_MIN_BARS, OVERLAY_MIN_ZONE_STRENGTH,
    OVERLAY_NEAREST_ZONES, OVERLAY_SETUPS_SCAN_BARS, OVERLAY_ZONE_OPACITY,
)

# One-slot cache: the chart modules build a fresh `df` per ticker and run
# every selected indicator against that same object before moving to the next
# ticker, so keying on id(df) avoids re-running the (swing detection + zone
# clustering) Analyzer once per selected DiNapoli layer.
_cache = {"key": None, "analyzer": None}


def _to_dinapoli_df(df: pd.DataFrame) -> pd.DataFrame:
    """Chart-side tidy (Date, Open, High, Low, Close[, Volume]) -> DiNapoli's
    expected (lowercase OHLC columns, DatetimeIndex)."""
    out = df.rename(columns=str.lower).copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(df["Date"]))
    return out[["open", "high", "low", "close"]]


def _analyzer(df: pd.DataFrame):
    """Cached Analyzer for this exact df object, or None if too little data."""
    if len(df) < OVERLAY_MIN_BARS:
        return None
    key = id(df)
    if _cache["key"] != key:
        _cache["key"] = key
        _cache["analyzer"] = Analyzer(_to_dinapoli_df(df), cfg=DINAPOLI_CONFIG)
    return _cache["analyzer"]


def _time_str(series) -> list:
    return pd.DatetimeIndex(pd.to_datetime(series)).strftime("%Y-%m-%d").tolist()


def _snap(times, date) -> str:
    """Latest chart date on or before `date` (weekly/monthly candles are dated
    by period end, which may be a weekend). Falls back to the first date."""
    if date is None:
        return times[0]
    key = pd.Timestamp(date).strftime("%Y-%m-%d")
    i = bisect_right(times, key) - 1
    return times[max(i, 0)]


def _series_from_column(df, times, column, title, color, pane="main"):
    vals = df[column]
    data = [{"time": t, "value": float(v)} for t, v in zip(times, vals) if pd.notna(v)]
    return {"title": title, "pane": pane, "type": "line", "color": color, "data": data}


def _zone_color(z):
    if z.is_expansion_cluster:
        return OVERLAY_COLORS["zone_expansion"]
    return OVERLAY_COLORS["zone_support" if z.direction == "support" else "zone_resistance"]


def _markers_series(title, color, by_key):
    """{(time, long_side): {..., "names": [...]}} -> one markers series,
    several events on the same bar/side merged into one '+'-joined label."""
    markers = []
    for m in by_key.values():
        m = dict(m)
        m["text"] = "+".join(dict.fromkeys(m.pop("names")))
        markers.append(m)
    markers.sort(key=lambda m: m["time"])
    return [{"title": title, "pane": "main", "type": "markers", "color": color, "data": markers}]


def _setup_name(setup):
    """Engine setup name -> label (the confluence bounce is 'Zgodnosc' there)."""
    return {"Zgodnosc": "Zgodność"}.get(setup.name, setup.name)


def _add_marker(by_key, time, up, color, name):
    key = (time, up)
    if key not in by_key:
        by_key[key] = {"time": time,
                       "position": "belowBar" if up else "aboveBar",
                       "color": color,
                       "shape": "arrowUp" if up else "arrowDown",
                       "names": []}
    by_key[key]["names"].append(name)


# --- Trend state (not a chart layer - used for badges and screener filters) -

def trend_summary(df):
    """{'D': ..., 'W': ..., 'M': ..., 'context': ...} for a tidy OHLC frame.

    Same Dow-style definition the Analyzer uses (services/dinapoli/trend.py),
    but without the Analyzer's indicator/level work, so it is cheap enough to
    run for every ticker of a screener universe. Unfinished weekly/monthly
    candles are excluded exactly like Analyzer._htf_slice() does. Returns None
    when there is too little data.
    """
    if df is None or len(df) < 30:
        return None
    d = _to_dinapoli_df(df).dropna()
    if len(d) < 30:
        return None
    cfg = DINAPOLI_CONFIG.swing
    out = {"D": trend_state(detect_swings(d, cfg))}
    last = d.index[-1]
    for rule in ("W", "M"):
        h = resample(d, rule)
        h = h[h.index <= last]
        out[rule] = trend_state(detect_swings(h, cfg)) if len(h) >= 10 else SIDE
    out["context"] = trend_alignment({k: out[k] for k in ("D", "W", "M")})
    return out


# --- Indicator functions, one per registry entry in services/indicators.py -

def _zone_bands(df, nearest):
    an = _analyzer(df)
    if an is None:
        return []
    snap = an.snapshot()
    times = _time_str(df["Date"])
    zones = [z for z in snap.zones if z.strength >= OVERLAY_MIN_ZONE_STRENGTH]
    if nearest:
        sup = sorted((z for z in zones if z.mid <= snap.price), key=lambda z: -z.mid)
        res = sorted((z for z in zones if z.mid > snap.price), key=lambda z: z.mid)
        zones = sup[:OVERLAY_NEAREST_ZONES] + res[:OVERLAY_NEAREST_ZONES]
    else:
        zones = sorted(zones, key=lambda z: -z.strength)[:OVERLAY_MAX_ZONES]
    bands = [{
        "start": _snap(times, z.origin_date),
        "end": times[-1],
        "top": float(z.high),
        "bottom": float(z.low),
        "color": _zone_color(z),
        "label": f"{z.pl_grade} {z.mid:.2f}",
        "detail": f"{z.pl_grade} {z.pl_names} {z.low:.2f}-{z.high:.2f} [siła {z.strength}]",
    } for z in zones]
    if not bands:
        return []
    return [{"title": "DiNapoli zones", "pane": "main", "type": "band",
             "color": OVERLAY_COLORS["zone_support"], "opacity": OVERLAY_ZONE_OPACITY,
             "data": bands}]


def dinapoli_zones(df):
    """Nearest Zgodność / Zgęszczenie / Kumulacja ekspansji bands around the
    last close (OVERLAY_NEAREST_ZONES below + above), drawn as shaded
    rectangles from the date the zone formed to the last bar."""
    return _zone_bands(df, nearest=True)


def dinapoli_zones_all(df):
    """Up to OVERLAY_MAX_ZONES strongest zones, regardless of distance."""
    return _zone_bands(df, nearest=False)


def dinapoli_levels(df):
    """Individual Fibonacci retracement (W3/W5) and expansion (BPD/PD/DPD) levels.

    Every swing on every timeframe produces its own set of levels, so this is
    filtered to the confluence engine's own proximity band around the last
    close (and capped) - otherwise 100+ lines pile onto the chart. Each line
    starts where its level became known (end of the swing / point C).
    """
    an = _analyzer(df)
    if an is None:
        return []
    snap = an.snapshot()
    band = snap.price * DINAPOLI_CONFIG.confluence.lookahead_pct
    nearby = [lv for lv in snap.levels if abs(lv.price - snap.price) <= band]
    nearby.sort(key=lambda lv: abs(lv.price - snap.price))

    times = _time_str(df["Date"])
    out = []
    for lv in nearby[:OVERLAY_MAX_LEVELS]:
        color = OVERLAY_COLORS["level_expansion" if lv.kind == "expansion" else "level_retracement"]
        t0 = _snap(times, lv.origin_date)
        out.append({"title": lv.pl_label, "pane": "main", "type": "line", "color": color,
                    "data": [{"time": t0, "value": float(lv.price)},
                             {"time": times[-1], "value": float(lv.price)}]})
    return out


def dinapoli_dma(df):
    """Displaced moving averages DMA 3x3 (fast) and DMA 25x5 (slow)."""
    an = _analyzer(df)
    if an is None:
        return []
    times = _time_str(df["Date"])
    return [
        _series_from_column(an.df, times, "dma_fast", "DMA 3x3", OVERLAY_COLORS["dma_fast"]),
        _series_from_column(an.df, times, "dma_slow", "DMA 25x5", OVERLAY_COLORS["dma_slow"]),
    ]


def dinapoli_macd_predictor(df):
    """MACD Predictor: price at which tomorrow's MACD crosses its signal line."""
    an = _analyzer(df)
    if an is None:
        return []
    times = _time_str(df["Date"])
    return [_series_from_column(an.df, times, "macd_pred", "MacdPred", OVERLAY_COLORS["macd_pred"])]


def dinapoli_overbought_oversold(df):
    """Oscillator Predictor: price bands for next-bar overbought/oversold."""
    an = _analyzer(df)
    if an is None:
        return []
    times = _time_str(df["Date"])
    return [
        _series_from_column(an.df, times, "osc_overbought", "Osc. overbought",
                            OVERLAY_COLORS["osc_overbought"]),
        _series_from_column(an.df, times, "osc_oversold", "Osc. oversold",
                            OVERLAY_COLORS["osc_oversold"]),
    ]


def _scanned_setups(an):
    """Every raw setup hit over the last OVERLAY_SETUPS_SCAN_BARS bars, cached
    on the Analyzer (the per-bar re-scan is the expensive part and both the
    setup and the failure layer need it).

    Uses Snapshot.setups (the raw scan_bar() hits) rather than Analyzer.scan()
    / .signal(). The latter is built for live trading - it keeps only the
    single highest-priority setup per bar and drops it if it fails the
    trend/overbought/RR filters. These overlays are for seeing what actually
    fired, so they bypass all of that.
    """
    cached = getattr(an, "_overlay_setups", None)
    if cached is not None:
        return cached
    start = max(0, len(an.df) - OVERLAY_SETUPS_SCAN_BARS)
    hits = []
    for i in range(start, len(an.df)):
        hits.extend(s for s in an.snapshot(i).setups if s.idx < len(an.df))
    an._overlay_setups = hits
    return hits


def dinapoli_setups(df):
    """Setup markers (B&B, DRePo, W&R, confluence bounce) over the recent window."""
    an = _analyzer(df)
    if an is None:
        return []
    times = _time_str(df["Date"])
    by_key = {}
    for s in _scanned_setups(an):
        long_side = s.side == "long"
        _add_marker(by_key, times[s.idx], long_side,
                    OVERLAY_COLORS["setup_long" if long_side else "setup_short"], _setup_name(s))
    return _markers_series("DiNapoli setups", OVERLAY_COLORS["setup_long"], by_key)


def dinapoli_failures(df):
    """"Niespełnienie" - a setup that failed: within OVERLAY_FAILURE_BARS after
    a long setup a close lands below the setup bar's low (short: above its
    high). The source treats this as a signal in the opposite direction, so
    the marker points that way ('✗DRePo' under a failed long = bearish)."""
    an = _analyzer(df)
    if an is None:
        return []
    times = _time_str(df["Date"])
    close, low, high = an.df["close"].to_numpy(), an.df["low"].to_numpy(), an.df["high"].to_numpy()
    n = len(close)
    by_key, seen = {}, set()
    for s in _scanned_setups(an):
        if (s.idx, s.name, s.side) in seen:
            continue
        seen.add((s.idx, s.name, s.side))
        long_side = s.side == "long"
        for j in range(s.idx + 1, min(n, s.idx + 1 + OVERLAY_FAILURE_BARS)):
            failed = close[j] < low[s.idx] if long_side else close[j] > high[s.idx]
            if failed:
                # Failed long -> bearish marker above the bar, and vice versa.
                _add_marker(by_key, times[j], not long_side, OVERLAY_COLORS["failure"],
                            f"✗{_setup_name(s)}")
                break
    return _markers_series("DiNapoli failures", OVERLAY_COLORS["failure"], by_key)


def dinapoli_breakouts(df):
    """"Wybicie" events over the last OVERLAY_EVENTS_SCAN_BARS bars: close
    crossing DMA 25x5, MacdPred, or one of the CURRENT zones (the zone set is
    today's - on older bars it shows where price crossed today's levels)."""
    an = _analyzer(df)
    if an is None:
        return []
    times = _time_str(df["Date"])
    d = an.df
    close = d["close"]
    start = max(1, len(d) - OVERLAY_EVENTS_SCAN_BARS)
    up_c, dn_c = OVERLAY_COLORS["breakout_up"], OVERLAY_COLORS["breakout_down"]
    by_key = {}

    for col, name in (("dma_slow", "DMA25x5"), ("macd_pred", "MacdPred")):
        above = close > d[col]
        valid = d[col].notna() & d[col].shift(1).notna()
        for i in range(start, len(d)):
            if valid.iloc[i] and above.iloc[i] != above.iloc[i - 1]:
                up = bool(above.iloc[i])
                _add_marker(by_key, times[i], up, up_c if up else dn_c,
                            f"{'↑' if up else '↓'}{name}")

    zones = [z for z in an.snapshot().zones if z.strength >= OVERLAY_MIN_ZONE_STRENGTH]
    for i in range(start, len(d)):
        prev, cur = close.iloc[i - 1], close.iloc[i]
        for z in zones:
            if prev <= z.high < cur:
                _add_marker(by_key, times[i], True, up_c, f"↑{z.pl_grade} {z.high:.2f}")
            elif prev >= z.low > cur:
                _add_marker(by_key, times[i], False, dn_c, f"↓{z.pl_grade} {z.low:.2f}")
    return _markers_series("DiNapoli breakouts", up_c, by_key)
