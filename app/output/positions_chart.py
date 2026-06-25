"""
TradingView-style chart for open positions.

Renders real OHLC data (via TradingView's open-source Lightweight Charts) for the
open positions, with custom indicators from the Python plugin registry
(app/services/indicators.py). Features:
  - collapsible left sidebar listing every open position with its daily % change
  - multi-ticker overlay (select several symbols at once)
  - candlestick / close-line chart-type switch
  - enable / disable all indicators at once
  - refresh that re-downloads OHLC into historical_prices_PROD.csv before display

Mirrors the module pattern of graph.py / trade_txn_editor.py:
`positions_chart_start(server=None)` builds a Dash app, optionally attached to a
shared Flask server, and runs standalone when no server is given.
"""

import os
from datetime import datetime

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State

import pandas as pd

from tickers_lists.ticker_groups import payloadPROD_db, payload_reit_db
from services.indicators import INDICATORS, compute_indicators
from services.market_metrics import download_ohlc_to_csv

# OHLC produced by procedure 4/7 (market_metrics.metrics_separate_tabs).
PROD_CSV = "historical_prices_PROD.csv"

# Distinct colours assigned to overlaid tickers (cycled if more are selected).
PALETTE = [
    "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
    "#0891b2", "#db2777", "#65a30d", "#0d9488", "#ea580c",
]


def _resolve_csv():
    """Find the PROD CSV relative to the cwd (like graph.py) or the repo root."""
    if os.path.exists(PROD_CSV):
        return PROD_CSV
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate = os.path.join(repo_root, PROD_CSV)
    return candidate if os.path.exists(candidate) else PROD_CSV


def _read_csv():
    try:
        return pd.read_csv(_resolve_csv())
    except FileNotFoundError:
        print(f"positions_chart: '{PROD_CSV}' not found.")
        return pd.DataFrame()


def load_ohlc(ticker, raw=None):
    """Return a tidy ascending OHLC DataFrame (Date, Open, High, Low, Close) for one ticker.

    Slices the wide historical_prices_PROD.csv (Open_T / High_T / Low_T / Close_T)
    and drops rows missing any OHLC value. `raw` lets a caller pass an already-read
    CSV to avoid re-reading per ticker. Returns an empty frame on any problem.
    """
    cols = ["Date", "Open", "High", "Low", "Close"]
    if not ticker:
        return pd.DataFrame(columns=cols)
    df = _read_csv() if raw is None else raw
    if df.empty:
        return pd.DataFrame(columns=cols)

    wide_cols = {f"{m}_{ticker}": m for m in ("Open", "High", "Low", "Close")}
    missing = [c for c in wide_cols if c not in df.columns]
    if "Date" not in df.columns or missing:
        return pd.DataFrame(columns=cols)

    out = df[["Date"] + list(wide_cols.keys())].rename(columns=wide_cols)
    out["Date"] = pd.to_datetime(out["Date"])
    out = out.dropna(subset=["Open", "High", "Low", "Close"]).sort_values("Date")
    return out.reset_index(drop=True)


def _candles(df):
    """Lightweight Charts candlestick payload: [{time, open, high, low, close}]."""
    times = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return [
        {"time": t, "open": float(o), "high": float(h), "low": float(low), "close": float(c)}
        for t, o, h, low, c in zip(times, df["Open"], df["High"], df["Low"], df["Close"])
    ]


def _line(df):
    """Lightweight Charts line payload from close prices: [{time, value}]."""
    times = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return [{"time": t, "value": float(c)} for t, c in zip(times, df["Close"])]


def _normalized_line(df, base):
    """Close prices rebased to % change from `base`: [{time, value}]."""
    times = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return [{"time": t, "value": (float(c) / base - 1.0) * 100.0}
            for t, c in zip(times, df["Close"])]


def daily_pct_changes(tickers, raw=None):
    """Map ticker -> latest daily % change (last close vs previous close)."""
    df = _read_csv() if raw is None else raw
    out = {}
    if df.empty:
        return out
    for t in tickers:
        col = f"Close_{t}"
        if col not in df.columns:
            continue
        closes = df[col].dropna()
        if len(closes) >= 2 and closes.iloc[-2] != 0:
            out[t] = (closes.iloc[-1] / closes.iloc[-2] - 1.0) * 100.0
    return out


def ath30_pct_map(tickers, raw=None):
    """Map ticker -> latest % distance from its 30-day rolling high.

    Mirrors the formula in app/output/graph.py / indicators.pct_from_ath30.
    """
    df = _read_csv() if raw is None else raw
    out = {}
    if df.empty:
        return out
    for t in tickers:
        col = f"Close_{t}"
        if col not in df.columns:
            continue
        closes = df[col].dropna()
        if closes.empty:
            continue
        ath30 = closes.rolling(window=30, min_periods=1).max()
        last_ath = ath30.iloc[-1]
        if last_ath:
            out[t] = (closes.iloc[-1] - last_ath) / last_ath * 100.0
    return out


def order_by_ath30(tickers, raw=None):
    """Return tickers sorted by % from 30-day ATH ascending (most below ATH first).

    Tickers with no computable value sort to the end (kept in original order).
    """
    pct = ath30_pct_map(tickers, raw=raw)
    return sorted(tickers, key=lambda t: (t not in pct, pct.get(t, 0.0)))


def _ticker_options(tickers, raw=None, reit_set=None):
    """Sidebar checklist options: 'TICKER  +1.2%' with red/green colouring."""
    pct = daily_pct_changes(tickers, raw=raw)
    reit_set = reit_set or set()
    options = []
    for t in tickers:
        p = pct.get(t)
        if p is None:
            chg_txt, color = "—", "#94a3b8"
        else:
            chg_txt = f"{p:+.2f}%"
            color = "#16a34a" if p >= 0 else "#dc2626"
        sym_children = [html.Span(t, className="pos-tk-sym")]
        if t in reit_set:
            sym_children.append(html.Span("REIT", className="pos-tk-reit"))
        label = html.Span(
            className="pos-tk-row",
            children=[
                html.Span(sym_children, className="pos-tk-left"),
                html.Span(chg_txt, className="pos-tk-chg", style={"color": color}),
            ],
        )
        options.append({"label": label, "value": t})
    return options


def positions_chart_start(server=None):
    app = dash.Dash(
        __name__,
        server=server if server is not None else True,
        url_base_pathname="/positions_chart/",
        assets_folder="assets_positions",
        title="Open Positions Chart",
    )

    open_positions = payloadPROD_db() or []
    reit_set = payload_reit_db()
    ordered_positions = order_by_ath30(open_positions)
    default_selection = ordered_positions[:1]
    default_indicators = [name for name, spec in INDICATORS.items() if spec["default_on"]]
    all_indicator_names = list(INDICATORS.keys())

    # Refresh state: download fresh OHLC once per process (so the first chart view
    # is up to date), and again whenever the user clicks Refresh.
    refresh_state = {"done": False}

    def refresh_csv():
        tickers = payloadPROD_db() or open_positions
        return download_ohlc_to_csv(tickers, _resolve_csv())

    app.layout = html.Div(
        className="pos-shell",
        children=[
            # --- Collapsible sidebar: every open position + daily % change -----
            html.Aside(
                id="pos-sidebar",
                className="pos-sidebar",
                children=[
                    html.Div(
                        className="pos-sidebar-head",
                        children=[
                            html.Div("Open positions", className="pos-sidebar-title"),
                            html.Div(
                                className="pos-sidebar-actions",
                                children=[
                                    html.Button("All", id="pos-tk-all", n_clicks=0,
                                                className="pos-mini-btn"),
                                    html.Button("None", id="pos-tk-none", n_clicks=0,
                                                className="pos-mini-btn"),
                                ],
                            ),
                        ],
                    ),
                    dcc.Checklist(
                        id="pos-hide-reit",
                        options=[{"label": "Disregard REITs", "value": "on"}],
                        value=[],
                        className="pos-hide-reit",
                    ),
                    dcc.Checklist(
                        id="pos-ticker-list",
                        options=_ticker_options(ordered_positions, reit_set=reit_set),
                        value=default_selection,
                        className="pos-ticker-list",
                    ),
                ],
            ),
            # --- Main column: top bar + chart ----------------------------------
            html.Div(
                className="pos-main",
                children=[
                    html.Div(
                        className="pos-topbar",
                        children=[
                            html.Button("☰", id="pos-sidebar-toggle",
                                        className="pos-icon-btn", n_clicks=0),
                            html.H1("Open Positions", className="pos-title"),
                            html.Div(
                                className="pos-control",
                                children=[
                                    html.Span("Scale", className="pos-label"),
                                    dcc.Checklist(
                                        id="pos-normalize",
                                        options=[{"label": "Normalize %", "value": "on"}],
                                        value=[],
                                        className="pos-radio",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="pos-control pos-indicators",
                                children=[
                                    html.Div(
                                        className="pos-label-row",
                                        children=[
                                            html.Span("Indicators", className="pos-label"),
                                            html.Button("All on/off", id="pos-ind-all",
                                                        n_clicks=0, className="pos-mini-btn"),
                                        ],
                                    ),
                                    dcc.Checklist(
                                        id="pos-candles",
                                        options=[{"label": "Candles", "value": "on"}],
                                        value=["on"],
                                        className="pos-checklist pos-candles",
                                    ),
                                    dcc.Checklist(
                                        id="pos-indicators",
                                        options=[{"label": n, "value": n} for n in all_indicator_names],
                                        value=default_indicators,
                                        className="pos-checklist",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="pos-control",
                                children=[
                                    html.Span("Data", className="pos-label"),
                                    html.Button("⟳ Refresh", id="pos-refresh", n_clicks=0,
                                                className="pos-refresh-btn"),
                                ],
                            ),
                            html.Span(id="pos-status", className="pos-status"),
                        ],
                    ),
                    html.Div(
                        className="pos-chart-wrap",
                        children=[html.Div(id="tv-chart")],
                    ),
                ],
            ),
            dcc.Store(id="tv-chart-data"),
            html.Div(id="tv-chart-dummy", style={"display": "none"}),
        ],
    )

    # --- Collapse / expand the sidebar -------------------------------------
    @app.callback(
        Output("pos-sidebar", "className"),
        Input("pos-sidebar-toggle", "n_clicks"),
        State("pos-sidebar", "className"),
        prevent_initial_call=True,
    )
    def toggle_sidebar(n_clicks, current):
        collapsed = "collapsed" in (current or "")
        return "pos-sidebar" if collapsed else "pos-sidebar collapsed"

    # --- Select all / none tickers (respecting the REIT filter) ------------
    @app.callback(
        Output("pos-ticker-list", "value"),
        [Input("pos-tk-all", "n_clicks"), Input("pos-tk-none", "n_clicks")],
        State("pos-hide-reit", "value"),
        prevent_initial_call=True,
    )
    def select_all_none(all_clicks, none_clicks, hide_reit):
        ctx = dash.callback_context
        triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
        if triggered != "pos-tk-all":
            return []
        if "on" in (hide_reit or []):
            return [t for t in open_positions if t not in reit_set]
        return open_positions

    # --- Enable / disable all indicators -----------------------------------
    @app.callback(
        Output("pos-indicators", "value"),
        Input("pos-ind-all", "n_clicks"),
        State("pos-indicators", "value"),
        prevent_initial_call=True,
    )
    def toggle_all_indicators(n_clicks, current):
        # If everything is already on, turn all off; otherwise turn all on.
        if set(current or []) >= set(all_indicator_names):
            return []
        return all_indicator_names

    # --- Build the chart payload -------------------------------------------
    @app.callback(
        [Output("tv-chart-data", "data"),
         Output("pos-status", "children"),
         Output("pos-ticker-list", "options")],
        [Input("pos-ticker-list", "value"),
         Input("pos-indicators", "value"),
         Input("pos-candles", "value"),
         Input("pos-normalize", "value"),
         Input("pos-hide-reit", "value"),
         Input("pos-refresh", "n_clicks")],
    )
    def build_chart_data(selected, selected_indicators, candles_value, normalize_value,
                         hide_reit_value, refresh_clicks):
        ctx = dash.callback_context
        triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""

        # Update the CSV before display: on the first load of this process, or
        # whenever Refresh is clicked. Other interactions reuse the cached CSV.
        status = dash.no_update
        do_refresh = triggered == "pos-refresh" or not refresh_state["done"]
        if do_refresh:
            ok = refresh_csv()
            refresh_state["done"] = True
            status = (f"Updated {datetime.now():%Y-%m-%d %H:%M:%S}"
                      if ok else "Refresh failed — showing cached data")

        hide_reit = "on" in (hide_reit_value or [])
        raw = _read_csv()
        # Rebuild the sidebar list when the data changed or the REIT filter toggled.
        if do_refresh or triggered == "pos-hide-reit":
            shown = order_by_ath30(open_positions, raw=raw)
            if hide_reit:
                shown = [t for t in shown if t not in reit_set]
            options = _ticker_options(shown, raw=raw, reit_set=reit_set)
        else:
            options = dash.no_update

        selected = selected or []
        if hide_reit:
            selected = [t for t in selected if t not in reit_set]
        chart_type = "candlestick" if "on" in (candles_value or []) else "line"
        normalize = "on" in (normalize_value or [])
        multi = len(selected) > 1

        price_series = []
        indicators_out = []
        for i, ticker in enumerate(selected):
            df = load_ohlc(ticker, raw=raw)
            if df.empty:
                continue
            color = PALETTE[i % len(PALETTE)]
            base = float(df["Close"].iloc[0]) if normalize else None
            if base:  # normalized line: rebased to % change from day 0
                price_series.append({"ticker": ticker, "type": "line", "color": color,
                                     "data": _normalized_line(df, base)})
            else:
                price_series.append({"ticker": ticker, "type": chart_type, "color": color,
                                     "data": _line(df) if chart_type == "line" else _candles(df)})

            # Indicators per ticker; prefix titles when overlaying several.
            for s in compute_indicators(df, selected_indicators or []):
                s["ticker"] = ticker
                # Rebase price-based (main-pane) indicators onto the same % scale
                # so SMA/EMA/ATH stay aligned with the normalized price line.
                if base and s["pane"] == "main" and s["type"] in ("line", "histogram"):
                    s["data"] = [{"time": d["time"], "value": (d["value"] / base - 1.0) * 100.0}
                                 for d in s["data"]]
                if multi and s["type"] != "markers":
                    s["title"] = f"{ticker} {s['title']}"
                indicators_out.append(s)

        data = {"chartType": chart_type, "normalized": normalize,
                "priceSeries": price_series, "indicators": indicators_out}
        return data, status, options

    # Hand the payload to Lightweight Charts (see assets_positions/tv_chart.js).
    app.clientside_callback(
        "window.dash_clientside.tvchart.render",
        Output("tv-chart-dummy", "children"),
        Input("tv-chart-data", "data"),
    )

    if not server:
        app.run(debug=True, use_reloader=False)
    return app


if __name__ == "__main__":
    positions_chart_start()
