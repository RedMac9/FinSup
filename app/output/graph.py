# Version of this module - bump on EVERY change to this file (see CLAUDE.md).
# MAJOR: breaking layout/behaviour change, MINOR: new feature, PATCH: fix.
#   1.0.0 - baseline (screener filters, indicator overlays, reload button)
#   1.1.0 - DiNapoli levels/zones drawn across the visible window (were
#           legend-only); one legend entry per ticker+indicator; version shown
#           in the top bar
#   1.2.0 - strategy-document features: D/W/M trend (dropdown labels, badges,
#           screener filters), volume-ratio filter, Daily/Weekly interval
#           switch, zones as shaded bands, stacked sub-panes for separate-pane
#           indicators (Volume, % from ATH30), volume bars, per-ticker
#           indicator cache (cleared on Reload Data)
#   1.3.0 - nav rail removed; drawer toggle (≡) moved into the top of the
#           "Ticker filters" drawer, "≡ Filters" button in the top bar
#           re-opens it while hidden
#   1.4.0 - Date Range: 30/90/180/360-day preset buttons and a calendar
#           range picker, kept in sync with the slider
__version__ = "1.4.0"

from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from tickers_lists.ticker_groups import payloadPROD_db
from services.indicators import INDICATORS, compute_indicators, resample_ohlc, volume_ratio
from services.dinapoli_overlay import trend_summary
from output.positions_chart import TREND_ARROWS, trend_badge

ALL_METRICS = ['Close', 'Open', 'High', 'Low']
OHLCV_METRICS = ['Open', 'High', 'Low', 'Close', 'Volume']
RANGE_PRESETS = (30, 90, 180, 360)   # "last N days" buttons next to the date slider
TREND_OPTIONS = [{'label': 'any', 'value': 'any'},
                 {'label': '↑ wzrostowy', 'value': 'wzrostowy'},
                 {'label': '↓ spadkowy', 'value': 'spadkowy'},
                 {'label': '→ boczny', 'value': 'boczny'}]
ALL_INDICATOR_NAMES = list(INDICATORS.keys())
DEFAULT_INDICATOR_NAMES = [name for name, spec in INDICATORS.items() if spec["default_on"]]


# --- Helper Functions ---


def _calculate_days_above_indicator(df, indicator_col, window_size):
    """Calculates the rolling sum of days a boolean indicator is True, per Ticker."""
    return df.groupby('Ticker')[indicator_col].transform(
        lambda x: x.rolling(window=window_size, min_periods=1).sum()
    )


def _create_filter_slider(label_text, slider_id, min_val, max_val, step, value, marks, style=None):
    """Creates a labeled Dash RangeSlider component."""
    return html.Div([
        html.Label(label_text, style={'fontWeight': 'bold'}),
        dcc.RangeSlider(
            id=slider_id,
            min=min_val,
            max=max_val,
            step=step,
            value=value,
            marks=marks,
            tooltip={"placement": "bottom", "always_visible": True}
        )
    ], style=style or {})


def _load_data(procedure_choice):
    """Reads the CSVs and DB fresh and returns a dict of everything the Dash layout/callbacks need."""
    # --- 1. Data Loading and Preparation ---
    open_positions = payloadPROD_db()

    # Map procedure choice to data files
    file_map = {
        "5": "historical_prices_GPW.csv",
        "6": "historical_prices_SP500.csv",
        "7": "historical_prices_PROD.csv",
        "13": "historical_prices_ETF.csv",
    }

    # Check for valid procedure choice
    if procedure_choice not in file_map:
        valid_choices = ", ".join(file_map.keys())
        print(f"Error: Invalid procedure_choice '{procedure_choice}'. Please use one of: {valid_choices}.")
        return

    # Load the main historical data CSV
    csv_file = file_map[procedure_choice]
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: '{csv_file}' not found.")
        print("Please make sure the CSV file is in the same directory as the script.")
        return

    # Convert 'Date' column to datetime objects
    if 'Date' not in df.columns:
        print("Error: Input CSV must contain a 'Date' column.")
        return

    df['Date'] = pd.to_datetime(df['Date'])

    # Reshape the data from wide to long format
    # Expecting columns like Close_AVGO, Open_AVGO, etc.
    df_melted = pd.melt(df, id_vars=['Date'], var_name='Metric_Ticker', value_name='Price')

    # Split combined column into separate 'Metric' and 'Ticker'
    if 'Metric_Ticker' not in df_melted.columns:
        print("Error: Melt step failed to create 'Metric_Ticker'. Check input column naming.")
        return

    split_cols = df_melted['Metric_Ticker'].str.split('_', n=1, expand=True)
    if split_cols.shape[1] != 2:
        print("Error: Could not split 'Metric_Ticker' into 'Metric' and 'Ticker'. Verify column names in input CSV.")
        return

    df_melted[['Metric', 'Ticker']] = split_cols
    df_melted.drop('Metric_Ticker', axis=1, inplace=True)

    # --- 1b. Merge ETF details if applicable ---
    if procedure_choice == "13":
        etf_details_file = 'app/tests/ETF.csv'
        try:
            etf_details_df = pd.read_csv(etf_details_file, delimiter=';')
        except FileNotFoundError:
            print(f"Error: '{etf_details_file}' not found.")
            print("Please make sure the CSV file is in the correct directory.")
            return

        # Ensure the join key in ETF details is as expected
        if 'Yfinance mapped' not in etf_details_df.columns:
            print("Error: ETF details file must contain 'Yfinance mapped' column.")
            return

        # Optional normalization of that key (strip spaces)
        etf_details_df['Yfinance mapped'] = etf_details_df['Yfinance mapped'].astype(str).str.strip()

        # De-duplicate right side on join key
        etf_details_df = etf_details_df.drop_duplicates(subset=['Yfinance mapped'], keep='first')

        # Ensure Theme and Country/Region exist (create if missing)
        for col in ['Theme', 'Country/Region']:
            if col not in etf_details_df.columns:
                etf_details_df[col] = None

        # Merge using left_on (Ticker) and right_on (Yfinance mapped)
        df_melted = pd.merge(
            df_melted,
            etf_details_df[['Yfinance mapped', 'Theme', 'Country/Region']],
            left_on='Ticker',
            right_on='Yfinance mapped',
            how='left'
        )
        # Drop helper key from right side to avoid duplicate ticker semantics
        df_melted.drop(columns=['Yfinance mapped'], inplace=True)

        # Prepare themes for filter
        all_themes = sorted(etf_details_df['Theme'].dropna().unique().tolist())
    else:
        all_themes = []

    # Ensure data is sorted by date and handle missing values
    df_melted.sort_values('Date', inplace=True)
    df_melted.dropna(subset=['Price'], inplace=True)

    # Get unique tickers for the controls
    if df_melted['Date'].empty:
        print("Error: No dates available after preprocessing.")
        return

    max_days = (df_melted['Date'].max() - df_melted['Date'].min()).days + 1
    max_days = max(max_days, 1)

    # --- 2. Pre-calculation for ATH Filter ---

    # Isolate close prices for ATH calculation
    close_prices_df = df_melted[df_melted['Metric'] == 'Close'].copy()

    if close_prices_df.empty:
        print("Warning: No 'Close' metric rows found. Filters dependent on Close will be empty.")

    # Calculate 30-day rolling ATH for each ticker
    if not close_prices_df.empty:
        close_prices_df['ath30'] = close_prices_df.groupby('Ticker')['Price'].transform(
            lambda x: x.rolling(window=30, min_periods=1).max()
        )
        # Calculate percentage difference from 30-day ATH
        close_prices_df['pct_diff_ath30'] = ((close_prices_df['Price'] - close_prices_df['ath30']) / close_prices_df['ath30']) * 100
        # Get the latest pct_diff for each ticker
        latest_pct_diff = close_prices_df.groupby('Ticker')['pct_diff_ath30'].last()
    else:
        latest_pct_diff = pd.Series(dtype='float64')

    # --- 2b. Pre-calculation for Days Close Above SMA/EMA ---

    if not close_prices_df.empty:
        # SMA10 / EMA10
        close_prices_df['SMA10'] = close_prices_df.groupby('Ticker')['Price'].transform(
            lambda x: x.rolling(window=10, min_periods=1).mean()
        )
        close_prices_df['EMA10'] = close_prices_df.groupby('Ticker')['Price'].transform(
            lambda x: x.ewm(span=10, adjust=False).mean()
        )

        close_prices_df['Close_Above_SMA10'] = close_prices_df['Price'] > close_prices_df['SMA10']
        close_prices_df['Close_Above_EMA10'] = close_prices_df['Price'] > close_prices_df['EMA10']

        close_prices_df['DaysCloseAboveSMA10_Last30'] = _calculate_days_above_indicator(close_prices_df, 'Close_Above_SMA10', 30)
        close_prices_df['DaysCloseAboveSMA10_Last90'] = _calculate_days_above_indicator(close_prices_df, 'Close_Above_SMA10', 90)
        close_prices_df['DaysCloseAboveEMA10_Last30'] = _calculate_days_above_indicator(close_prices_df, 'Close_Above_EMA10', 30)

        # SMA20 / EMA32 (new)
        close_prices_df['SMA20'] = close_prices_df.groupby('Ticker')['Price'].transform(
            lambda x: x.rolling(window=20, min_periods=1).mean()
        )
        close_prices_df['EMA32'] = close_prices_df.groupby('Ticker')['Price'].transform(
            lambda x: x.ewm(span=32, adjust=False).mean()
        )

        close_prices_df['Close_Above_SMA20'] = close_prices_df['Price'] > close_prices_df['SMA20']
        close_prices_df['Close_Above_EMA32'] = close_prices_df['Price'] > close_prices_df['EMA32']

        close_prices_df['DaysCloseAboveSMA20_Last30'] = _calculate_days_above_indicator(close_prices_df, 'Close_Above_SMA20', 30)
        close_prices_df['DaysCloseAboveEMA32_Last30'] = _calculate_days_above_indicator(close_prices_df, 'Close_Above_EMA32', 30)

        # --- New: Days Close Above Last Day High ---
        high_prices_df = df_melted[df_melted['Metric'] == 'High'].copy()
        high_prices_df = high_prices_df[['Date', 'Ticker', 'Price']].rename(columns={'Price': 'High'})
        close_prices_df = pd.merge(close_prices_df, high_prices_df, on=['Date', 'Ticker'], how='left')
        close_prices_df['PrevHigh'] = close_prices_df.groupby('Ticker')['High'].shift(1)
        close_prices_df['Close_Above_PrevHigh'] = close_prices_df['Price'] > close_prices_df['PrevHigh']
        close_prices_df['DaysCloseAboveHigh_Last30'] = _calculate_days_above_indicator(close_prices_df, 'Close_Above_PrevHigh', 30)

        # Latest values for each ticker
        latest_days_above_sma30 = close_prices_df.groupby('Ticker')['DaysCloseAboveSMA10_Last30'].last()
        latest_days_above_sma90 = close_prices_df.groupby('Ticker')['DaysCloseAboveSMA10_Last90'].last()
        latest_days_above_ema30 = close_prices_df.groupby('Ticker')['DaysCloseAboveEMA10_Last30'].last()

        # New latest series
        latest_days_above_sma20_30 = close_prices_df.groupby('Ticker')['DaysCloseAboveSMA20_Last30'].last()
        latest_days_above_ema32_30 = close_prices_df.groupby('Ticker')['DaysCloseAboveEMA32_Last30'].last()
        latest_days_above_high30 = close_prices_df.groupby('Ticker')['DaysCloseAboveHigh_Last30'].last()
    else:
        latest_days_above_sma30 = pd.Series(dtype='float64')
        latest_days_above_sma90 = pd.Series(dtype='float64')
        latest_days_above_ema30 = pd.Series(dtype='float64')
        # New empty series
        latest_days_above_sma20_30 = pd.Series(dtype='float64')
        latest_days_above_ema32_30 = pd.Series(dtype='float64')
        latest_days_above_high30 = pd.Series(dtype='float64')

    # For ETF themes: latest theme per ticker if present
    if procedure_choice == "13":
        latest_theme = df_melted.groupby('Ticker')['Theme'].last()
        # Per-ticker ETF details for the chart hover (price rows are rebuilt
        # from the wide frame in update_graph, so they don't carry these).
        ticker_meta = df_melted.groupby('Ticker')[['Theme', 'Country/Region']].last()
    else:
        latest_theme = pd.Series(dtype='object')
        ticker_meta = None

    # Create a list of dictionaries containing ticker info for the dropdown
    ticker_info = []
    for ticker, pct_diff in latest_pct_diff.items():
        days_above_sma30 = latest_days_above_sma30.get(ticker, 0)
        days_above_sma90 = latest_days_above_sma90.get(ticker, 0)
        days_above_ema30 = latest_days_above_ema30.get(ticker, 0)
        days_above_sma20_30 = latest_days_above_sma20_30.get(ticker, 0)
        days_above_ema32_30 = latest_days_above_ema32_30.get(ticker, 0)
        days_above_high30 = latest_days_above_high30.get(ticker, 0)

        # D/W/M trend (strategy document's primary context) + volume vs its
        # 20-day average ("na większych obrotach").
        ohlc = _wide_ohlc(df, ticker)
        trend = trend_summary(ohlc)
        vol_ratio = volume_ratio(ohlc)
        trend_txt = (" ".join(f"{tf}{TREND_ARROWS.get(trend[tf], ('?',))[0]}" for tf in ("D", "W", "M"))
                     if trend else "trend ?")
        vol_txt = f", Vol×{vol_ratio:.1f}" if vol_ratio is not None else ""

        label = (
            f"{ticker} [{trend_txt}] (ATH: {pct_diff:.1f}%, "
            f"EMA30: {days_above_ema30:.0f}d, "
            f"SMA30: {days_above_sma30:.0f}d, "
            f"SMA90: {days_above_sma90:.0f}d, "
            f"SMA20-30d: {days_above_sma20_30:.0f}d, "
            f"EMA32-30d: {days_above_ema32_30:.0f}d, "
            f"High30: {days_above_high30:.0f}d{vol_txt})"
        )

        info = {
            'label': label,
            'value': ticker,
            'pct_diff': float(pct_diff) if pd.notna(pct_diff) else -1e9,
            'days_above_sma30': float(days_above_sma30) if pd.notna(days_above_sma30) else 0.0,
            'days_above_sma90': float(days_above_sma90) if pd.notna(days_above_sma90) else 0.0,
            'days_above_ema30': float(days_above_ema30) if pd.notna(days_above_ema30) else 0.0,
            'days_above_sma20_30': float(days_above_sma20_30) if pd.notna(days_above_sma20_30) else 0.0,
            'days_above_ema32_30': float(days_above_ema32_30) if pd.notna(days_above_ema32_30) else 0.0,
            'days_above_high30': float(days_above_high30) if pd.notna(days_above_high30) else 0.0,
            'trend': trend,
            'vol_ratio': vol_ratio,
        }
        if procedure_choice == "13":
            info['theme'] = latest_theme.get(ticker, 'N/A')
        ticker_info.append(info)


    # Sort ticker_info by pct_diff descending
    ticker_info = sorted(ticker_info, key=lambda x: x['pct_diff'], reverse=True)

    return {
        'df_wide': df,
        'ticker_meta': ticker_meta,
        'df_melted': df_melted,
        'close_prices_df': close_prices_df,
        'ticker_info': ticker_info,
        'all_themes': all_themes,
        'max_days': max_days,
        'open_positions': open_positions,
        'loaded_at': datetime.now(),
    }


def _wide_ohlc(df_wide, ticker):
    """Tidy (Date, Open, High, Low, Close[, Volume]) for one ticker, sliced
    straight from the wide historical_prices_*.csv frame - much faster than
    filtering the melted frame, which matters because every screener ticker
    is touched at load (trend state, volume ratio). Uses the ticker's whole
    loaded history, so rolling/EMA indicators have enough lookback right from
    the first visible bar - the resulting series are trimmed to the window
    afterwards.
    """
    cols = {f"{m}_{ticker}": m for m in OHLCV_METRICS if f"{m}_{ticker}" in df_wide.columns}
    if 'Close' not in cols.values():
        return pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close'])
    out = df_wide[['Date'] + list(cols)].rename(columns=cols)
    price_cols = [c for c in ('Open', 'High', 'Low', 'Close') if c in out.columns]
    return out.dropna(subset=price_cols).sort_values('Date').reset_index(drop=True)


def _price_rows(ohlc, ticker, metrics):
    """Tidy OHLC -> long (Date, Metric, Ticker, Price) rows, the shape the
    px.line price chart is built from."""
    keep = [m for m in metrics if m in ohlc.columns]
    rows = ohlc.melt(id_vars=['Date'], value_vars=keep, var_name='Metric', value_name='Price')
    rows['Ticker'] = ticker
    return rows.dropna(subset=['Price'])


def _rgba(hex_color, alpha):
    h = (hex_color or '#64748b').lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alpha})'


def _indicator_traces(ticker, ohlc, selected_indicators, base, start_date, end_date,
                      cache=None, cache_key=None):
    """Plotly traces for one ticker's selected indicators (see
    services/indicators.py - the same registry app/output/positions_chart.py
    uses), rebased onto the chart's normalized '% change from day 0' scale
    and clipped to the visible date range. `ohlc` is the ticker's tidy frame
    at the displayed interval (daily or weekly).

    Marker-type series (EMA32 cross, DiNapoli setups, ...) carry a date and
    an up/down side but no y-value - there's no OHLC bar to anchor "above"/
    "below" to on this line chart, so they're placed just off the ticker's
    own normalized price line at that date instead.

    Traces of pane="separate" series carry meta={'pane': ...}; update_graph()
    moves them onto their own stacked y-axis.
    """
    if not selected_indicators or not base or ohlc is None or ohlc.empty:
        return []

    norm_price = (ohlc.set_index('Date')['Close'] / base - 1.0) * 100.0

    traces = []
    # One indicator per compute_indicators() call so every series it returns
    # (e.g. 20 DiNapoli level lines) can share a single legend entry/group.
    for ind_name in selected_indicators:
        # Series depend only on the ticker's data + interval, not on the
        # visible window/base, so they're cached (the DiNapoli setup layer
        # re-scans bar by bar and takes seconds on 3 years of data).
        key = (cache_key, ind_name)
        if cache is not None and key in cache:
            series = cache[key]
        else:
            series = compute_indicators(ohlc, [ind_name])
            if cache is not None:
                cache[key] = series
        traces.extend(_series_traces(ticker, ind_name, series, norm_price,
                                     base, start_date, end_date))
    return traces


def _series_traces(ticker, ind_name, series, norm_price, base, start_date, end_date):
    """Plotly traces for the series dicts of one indicator. All traces share
    the legend group '<TICKER> <indicator>'; only the first shows in the legend.
    """
    group = f"{ticker} {ind_name}"
    traces = []

    def legend():
        return dict(legendgroup=group, showlegend=not traces)

    def rebase_price(v):
        return (v / base - 1.0) * 100.0

    for s in series:
        name = f"{ticker} {s['title']}"
        label = group if len(series) > 1 else name

        if s['type'] == 'band':
            # Shaded zone rectangle from the date the zone formed (or the
            # window start) to the window end, with its label at the top-left.
            fill = s.get('opacity', 0.18)
            for b in s['data']:
                x0, x1 = max(pd.to_datetime(b['start']), start_date), end_date
                if x0 > x1:
                    continue
                top, bot = rebase_price(b['top']), rebase_price(b['bottom'])
                traces.append(go.Scatter(
                    x=[x0, x1, x1, x0, x0], y=[bot, bot, top, top, bot],
                    mode='lines', fill='toself', fillcolor=_rgba(b['color'], fill),
                    line=dict(width=0), name=group, hoverinfo='skip', **legend(),
                ))
                traces.append(go.Scatter(
                    x=[x0], y=[top], mode='text', text=[b['label']],
                    textposition='top right', textfont=dict(size=10, color=b['color']),
                    name=group, legendgroup=group, showlegend=False,
                    hovertemplate=f"{ticker} {b['detail']}<extra></extra>",
                ))
            continue

        if s['type'] == 'markers':
            xs, ys, texts, symbols, colors = [], [], [], [], []
            times = pd.to_datetime([m['time'] for m in s['data']])
            for t, m in zip(times, s['data']):
                if t < start_date or t > end_date or t not in norm_price.index:
                    continue
                offset = -2.5 if m['position'] == 'belowBar' else 2.5
                xs.append(t)
                ys.append(norm_price.loc[t] + offset)
                texts.append(m['text'])
                symbols.append('triangle-up' if m['shape'] == 'arrowUp'
                              else 'triangle-down' if m['shape'] == 'arrowDown'
                              else 'circle')
                colors.append(m['color'])
            if not xs:
                continue
            traces.append(go.Scatter(
                x=xs, y=ys, mode='markers', name=label, **legend(),
                marker=dict(symbol=symbols, color=colors, size=9,
                           line=dict(width=1, color='#1f2937')),
                text=texts,
                hovertemplate=f'{name}<br>%{{text}}<br>%{{x|%Y-%m-%d}}<extra></extra>',
            ))
            continue

        # Line/histogram series: price-scale ones ("main" pane) get rebased
        # the same way the price line itself is, so e.g. SMA20 stays glued
        # to the % line instead of floating off in raw price units. Anything
        # in its own pane (pane="separate", e.g. Volume, "% from ATH30") keeps
        # its units and goes on its own y-axis.
        #
        # Horizontal lines (DiNapoli levels) are sent as just two points -
        # where the level was born and the last date. Plain clipping would
        # drop the first one when it's before the visible window, leaving a
        # single point that plotly can't draw as a line, so those are
        # clamped to the window edges instead.
        separate = s['pane'] == 'separate'
        rebase = (lambda v: v) if separate else rebase_price
        data = s['data']
        values = {d['value'] for d in data}
        colors = None
        if len(data) >= 2 and len(values) == 1:
            t_first = max(pd.to_datetime(data[0]['time']), start_date)
            t_last = min(pd.to_datetime(data[-1]['time']), end_date)
            if t_first > t_last:
                continue
            xs = [t_first, t_last]
            ys = [rebase(data[0]['value'])] * 2
        else:
            # Parse all dates in one call - per-point pd.to_datetime() made
            # this the slowest part of the callback on 3 years of history.
            times = pd.to_datetime([d['time'] for d in data])
            keep = [i for i, t in enumerate(times) if start_date <= t <= end_date]
            xs = [times[i] for i in keep]
            ys = [rebase(data[i]['value']) for i in keep]
            colors = [data[i].get('color', s['color']) for i in keep]
        if not xs:
            continue
        meta = {'pane': group} if separate else None
        if s['type'] == 'histogram' and separate:
            traces.append(go.Bar(
                x=xs, y=ys, name=label, marker_color=colors or s['color'], meta=meta,
                **legend(),
                hovertemplate=f'{name}<br>%{{y:,.0f}}<br>%{{x|%Y-%m-%d}}<extra></extra>',
            ))
            continue
        traces.append(go.Scatter(
            x=xs, y=ys, mode='lines', name=label, meta=meta, **legend(),
            line=dict(color=s['color'], width=1.3,
                     dash='dot' if s['type'] == 'histogram' else 'solid'),
            hovertemplate=f'{name}<br>%{{y:.2f}}<br>%{{x|%Y-%m-%d}}<extra></extra>',
        ))
    return traces


def _stack_panes(fig):
    """Move every trace tagged meta={'pane': key} onto its own y-axis, stacked
    as strips under the main price axis (one strip per ticker+indicator)."""
    keys = []
    for tr in fig.data:
        key = (tr.meta or {}).get('pane') if isinstance(tr.meta, dict) else None
        if key and key not in keys:
            keys.append(key)
    if not keys:
        return
    n = len(keys)
    strip = min(0.2, 0.45 / n)
    fig.update_layout(yaxis=dict(domain=[n * strip + 0.03, 1.0]))
    for i, key in enumerate(keys):
        axis_no = i + 2
        lo = (n - i - 1) * strip
        fig.update_layout(**{f'yaxis{axis_no}': dict(
            domain=[lo, lo + strip - 0.015], anchor='x', showgrid=False,
            title=dict(text=key, font=dict(size=9)), tickfont=dict(size=9),
        )})
        for tr in fig.data:
            if isinstance(tr.meta, dict) and tr.meta.get('pane') == key:
                tr.update(yaxis=f'y{axis_no}')
    # x-axis labels under the bottom strip rather than under the price axis.
    fig.update_layout(xaxis=dict(anchor=f'y{n + 1}'), barmode='overlay')


def graph_start(procedure_choice, def_filter_graph_list, server=None):
    data = _load_data(procedure_choice)
    if data is None:
        return
    state = dict(data)

    # --- 3. Initialize the Dash App ---
    app = dash.Dash(
        __name__,
        server=server if server is not None else True,
        url_base_pathname=f'/graph/{procedure_choice}/'
    )

    # --- 4. Define the App Layout ---

    # Determine the initial value for the dropdown before defining the layout
    if procedure_choice == "7":
        initial_dropdown_value = def_filter_graph_list or []
    else:
        initial_dropdown_value = ['AVGO', 'CRWD']

    # Theme filter layout (always present in tree for callbacks, visually hidden when not ETF)
    theme_filter_layout = html.Div(
        className="filter-item",
        style={'display': 'block' if procedure_choice == "13" else 'none'},
        children=[
            html.Label("Filter by Theme:", className="field-label"),
            dcc.Dropdown(
                id='theme-filter-dropdown',
                options=[{'label': theme, 'value': theme} for theme in state['all_themes']],
                multi=True,
                placeholder="Select themes...",
                className="m3-dropdown"
            )
        ])

    app.layout = html.Div(
        className="app-shell",
        id="app-shell",
        children=[
            dcc.Store(id='drawer-state', data={'visible': True}),
            # Drawer
            html.Aside(
                className="filter-drawer",
                id="filter-drawer",
                children=[
                    html.Div(
                        className="drawer-header",
                        children=[
                            html.Button("≡", className="drawer-toggle", id="drawer-toggle",
                                        title="Hide ticker filters"),
                            html.H1("Ticker filters", className="drawer-title"),
                        ],
                    ),
                    # Core Filters Section
                    html.Div(
                        className="drawer-section",
                        id="section-core-filters",
                        children=[
                            html.Div("Core filters", className="section-label"),
                            html.Div(
                                className="m3-card stack-lg",
                                children=[
                                    # ATH Filter
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="filter-row",
                                                children=[
                                                    html.Label("% from 30-Day ATH", className="field-label"),
                                                ],
                                            ),
                                            dcc.RangeSlider(
                                                id="ath-filter-slider",
                                                min=-100, max=0, step=1, value=[-50, 0],
                                                marks={i: f"{i}%" for i in range(-100, 1, 20)},
                                                tooltip={"placement": "bottom", "always_visible": False},
                                            ),
                                        ],
                                    ),
                                    # SMA10 30d
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Label("Days Above SMA10 (30d)", className="field-label"),
                                            dcc.RangeSlider(
                                                id="sma-filter-slider",
                                                min=0, max=30, step=1, value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    # EMA10 30d
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Label("Days Above EMA10 (30d)", className="field-label"),
                                            dcc.RangeSlider(
                                                id="ema-filter-slider",
                                                min=0, max=30, step=1, value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    # SMA10 90d
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Label("Days Above SMA10 (90d)", className="field-label"),
                                            dcc.RangeSlider(
                                                id="sma90-filter-slider",
                                                min=0, max=90, step=1, value=[0, 90],
                                                marks={i: str(i) for i in range(0, 91, 30)},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Advanced Filtering Section
                    html.Div(
                        className="drawer-section",
                        children=[
                            html.Div("Advanced filtering", className="section-label"),
                            html.Div(
                                className="m3-card stack-lg",
                                children=[
                                    # SMA20 30d
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Label("Days Above SMA20 (30d)", className="field-label"),
                                            dcc.RangeSlider(
                                                id="sma20-30-filter-slider",
                                                min=0, max=30, step=1, value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    # EMA32 30d
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Label("Days Above EMA32 (30d)", className="field-label"),
                                            dcc.RangeSlider(
                                                id="ema32-30-filter-slider",
                                                min=0, max=30, step=1, value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    # High30 30d
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Label("Days Close Above Last High (30d)", className="field-label"),
                                            dcc.RangeSlider(
                                                id="high30-filter-slider",
                                                min=0, max=30, step=1, value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    # D/W/M trend (Dow-style, from DiNapoli swings)
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div("Trend (D / W / M)", className="field-label block"),
                                            html.Div(
                                                className="grid-2",
                                                children=[
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label(f"Trend {tf}", className="mini-label"),
                                                            dcc.Dropdown(id=f"trend-{tf.lower()}-filter",
                                                                         options=TREND_OPTIONS, value="any",
                                                                         clearable=False, className="m3-dropdown"),
                                                        ],
                                                    )
                                                    for tf in ("D", "W", "M")
                                                ] + [
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Min volume × avg20", className="mini-label"),
                                                            dcc.Input(id="volume-ratio-input", type="number",
                                                                      value=None, min=0, step=0.1,
                                                                      placeholder="off", className="m3-input"),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    # Price Change Filters
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div("Price Change Filters", className="field-label block"),
                                            html.Div(
                                                className="grid-2",
                                                children=[
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Lookback 1", className="mini-label"),
                                                            dcc.Input(id="price-change-days-input-1", type="number", value=30, min=1, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Min % 1", className="mini-label"),
                                                            dcc.Input(id="price-change-pct-input-1", type="number", value=-100, min=-100, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Lookback 2", className="mini-label"),
                                                            dcc.Input(id="price-change-days-input-2", type="number", value=90, min=1, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Min % 2", className="mini-label"),
                                                            dcc.Input(id="price-change-pct-input-2", type="number", value=-100, min=-100, className="m3-input"),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    # ATH Drop Filter
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="toggle-row",
                                                children=[
                                                    html.Div(
                                                        children=[
                                                            html.Div("ATH Drop Filter", className="field-label"),
                                                            html.Div("Dynamic drop logic", className="support-text"),
                                                        ]
                                                    ),
                                                    dcc.Checklist(
                                                        id="ath-drop-enable",
                                                        options=[{"label": "Enabled", "value": "enabled"}],
                                                        value=[],
                                                        className="toggle-checklist",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="grid-2",
                                                children=[
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("ATH lookback", className="mini-label"),
                                                            dcc.Input(id="ath-drop-days-slider", type="number", value=90, min=10, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Max overrides", className="mini-label"),
                                                            dcc.Input(id="ath-drop-bypass-count", type="number", value=0, min=0, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Standard drop %", className="mini-label"),
                                                            dcc.Input(id="ath-drop-std-pct-slider", type="number", value=6.5, min=0, step=0.5, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Override drop %", className="mini-label"),
                                                            dcc.Input(id="ath-drop-override-pct-slider", type="number", value=12.0, min=0, step=0.5, className="m3-input"),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            dcc.Checklist(
                                                id="open-positions-filter",
                                                options=[{"label": "Disable open positions", "value": "enabled"}],
                                                value=[],
                                                className="toggle-checklist secondary-toggle",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Ticker Selection Section
                    html.Div(
                        className="drawer-section",
                        id="section-ticker-selection",
                        children=[
                            html.Div("Ticker selection", className="section-label"),
                            html.Div(
                                className="m3-card stack-md",
                                children=[
                                    theme_filter_layout,
                                    dcc.Dropdown(
                                        id="ticker-dropdown",
                                        options=[{'label': t['label'], 'value': t['value']} for t in state['ticker_info']],
                                        value=initial_dropdown_value,
                                        multi=True,
                                        className="m3-dropdown",
                                    ),
                                    html.Button("Select all filtered", id="select-all-button", className="btn-tonal block-btn"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            # Main Content
            html.Main(
                className="main-content",
                children=[
                    # Top Bar
                    html.Header(
                        className="top-app-bar",
                        id="section-dashboard",
                        children=[
                            html.Div(
                                className="title-block",
                                children=[
                                    # Only shown while the filter drawer is hidden
                                    # (its own ≡ toggle is then off-screen).
                                    html.Button("≡ Filters", id="drawer-open", className="btn-tonal drawer-open",
                                                style={'display': 'none'}, title="Show ticker filters"),
                                    html.Div(f"Stock Ticker Performance Analysis · graph.py v{__version__}", className="top-caption"),
                                    html.H2("Dashboard", className="top-title"),
                                    html.Div(
                                        [
                                            html.Button("Reload Data", id="reload-data-button", className="btn-tonal", n_clicks=0),
                                            html.Span(
                                                f"Loaded at {state['loaded_at'].strftime('%Y-%m-%d %H:%M:%S')}",
                                                id="reload-status",
                                                className="mini-label",
                                                style={'marginLeft': '10px'},
                                            ),
                                        ],
                                        style={'marginTop': '8px'},
                                    ),
                                    dcc.Interval(id="initial-load-trigger", interval=500, max_intervals=1),
                                ],
                            ),
                            html.Div(
                                className="top-actions",
                                children=[
                                    dcc.Dropdown(
                                        id="metric-checklist",
                                        options=[{"label": m, "value": m} for m in ALL_METRICS],
                                        value=["Close"],
                                        multi=True,
                                        className="compact-dropdown",
                                    ),
                                    dcc.RadioItems(
                                        id="interval-radio",
                                        options=[{"label": "D", "value": "D"},
                                                 {"label": "W", "value": "W"}],
                                        value="D",
                                        inline=True,
                                        className="toggle-checklist",
                                    ),
                                    dcc.Dropdown(
                                        id="indicator-checklist",
                                        options=[{"label": n, "value": n} for n in ALL_INDICATOR_NAMES],
                                        value=DEFAULT_INDICATOR_NAMES,
                                        multi=True,
                                        placeholder="Indicators...",
                                        className="compact-dropdown",
                                    ),
                                    html.Div([
                                        html.Div(
                                            className="date-range-head",
                                            children=[
                                                html.Label("Date Range:", className="mini-label"),
                                                html.Div(
                                                    className="range-presets",
                                                    children=[
                                                        html.Button(f"{n}d", id=f"range-{n}", n_clicks=0,
                                                                    className="range-btn active" if n == 30 else "range-btn",
                                                                    title=f"Last {n} days")
                                                        for n in RANGE_PRESETS
                                                    ],
                                                ),
                                                dcc.DatePickerRange(
                                                    id="date-picker",
                                                    min_date_allowed=state['df_melted']['Date'].min().date(),
                                                    max_date_allowed=state['df_melted']['Date'].max().date(),
                                                    start_date=(state['df_melted']['Date'].min()
                                                                + pd.Timedelta(days=max(0, state['max_days'] - 30))).date(),
                                                    end_date=state['df_melted']['Date'].max().date(),
                                                    display_format='YYYY-MM-DD',
                                                    first_day_of_week=1,
                                                    minimum_nights=0,
                                                    className="date-picker",
                                                ),
                                            ],
                                        ),
                                        dcc.RangeSlider(
                                            id="days-slider",
                                            min=0,
                                            max=state['max_days'] - 1,
                                            value=[max(0, state['max_days'] - 30), state['max_days'] - 1],
                                            step=1,
                                            marks={
                                                0: (state['df_melted']['Date'].min()).strftime('%Y-%m-%d'),
                                                state['max_days'] - 1: (state['df_melted']['Date'].max()).strftime('%Y-%m-%d')
                                            },
                                            className="compact-range-slider"
                                        ),
                                        html.Div(id="date-range-count", className="mini-label", style={'textAlign': 'center', 'marginTop': '4px'})
                                    ], style={'flex': '1', 'minWidth': '300px', 'marginLeft': '20px'}),
                                ],
                            ),
                        ],
                    ),
                    # Scrollable Content
                    html.Div(
                        className="page-scroll",
                        children=[
                            # Graph Section
                            html.Section(
                                className="analytics-grid",
                                id="section-chart",
                                style={'gridTemplateColumns': '1fr'},
                                children=[
                                    html.Div(
                                        className="panel-card",
                                        children=[
                                            html.Div(
                                                className="panel-head",
                                                children=[
                                                    html.Div(children=[html.H3("Price performance", className="panel-title"), html.P("Normalized performance visualization.", className="panel-copy")]),
                                                    html.Div("Live selection", className="state-chip"),
                                                ],
                                            ),
                                            html.Div(id="trend-badges", className="trend-row"),
                                            dcc.Graph(id="price-performance-graph", style={'height': '70vh'}, className="graph-frame"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            # Store hidden tickers
            dcc.Store(id='hidden-traces-store', data=[]),
        ],
    )

    # --- 5. Define Callbacks ---

    @app.callback(
        [Output('app-shell', 'style'),
         Output('filter-drawer', 'style'),
         Output('drawer-state', 'data'),
         Output('drawer-open', 'style')],
        [Input('drawer-toggle', 'n_clicks'),
         Input('drawer-open', 'n_clicks')],
        [State('drawer-state', 'data')]
    )
    def toggle_drawer(toggle_clicks, open_clicks, state):
        ctx = dash.callback_context
        triggered = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else ''

        visible = state['visible']
        if triggered == 'drawer-toggle':
            visible = not visible
        elif triggered == 'drawer-open':
            visible = True

        shell_style = {
            'gridTemplateColumns': f"{'392px' if visible else '0px'} minmax(0, 1fr)",
            'transition': 'grid-template-columns 0.3s ease',
        }

        drawer_style = {
            'display': 'block', # Keep in grid to maintain column mapping
            'visibility': 'visible' if visible else 'hidden',
            # X stays clipped so collapsing to 0px never shows a horizontal
            # scrollbar; Y needs to scroll when open, or content taller than
            # the viewport (e.g. the "Universe" ticker-selection section) is
            # simply unreachable - 'overflow: hidden' on both axes was the
            # previous behaviour and blocked that.
            'overflowX': 'hidden',
            'overflowY': 'auto' if visible else 'hidden',
            'width': '392px' if visible else '0px',
            'transition': 'width 0.3s, visibility 0.3s',
        }

        open_style = {'display': 'none'} if visible else {'display': 'inline-block', 'marginBottom': '8px'}
        return shell_style, drawer_style, {'visible': visible}, open_style

    @app.callback(
        Output('ticker-dropdown', 'options'),
        [
            Input('ath-filter-slider', 'value'),
            Input('sma-filter-slider', 'value'),
            Input('ema-filter-slider', 'value'),
            Input('sma90-filter-slider', 'value'),
            Input('sma20-30-filter-slider', 'value'),
            Input('ema32-30-filter-slider', 'value'),
            Input('high30-filter-slider', 'value'),
            Input('theme-filter-dropdown', 'value'),
            Input('open-positions-filter', 'value'),
            Input('ath-drop-enable', 'value'),
            Input('ath-drop-days-slider', 'value'),
            Input('ath-drop-std-pct-slider', 'value'),
            Input('ath-drop-override-pct-slider', 'value'),
            Input('ath-drop-bypass-count', 'value'),
            Input('price-change-days-input-1', 'value'),
            Input('price-change-pct-input-1', 'value'),
            Input('price-change-days-input-2', 'value'),
            Input('price-change-pct-input-2', 'value'),
            Input('trend-d-filter', 'value'),
            Input('trend-w-filter', 'value'),
            Input('trend-m-filter', 'value'),
            Input('volume-ratio-input', 'value'),
            # Re-run after a data reload so options reflect the fresh state.
            Input('reload-status', 'children'),
        ]
    )
    def update_dropdown_options(ath_slider_range, sma30_slider_range, ema30_slider_range, sma90_slider_range,
                                sma20_30_slider_range, ema32_30_slider_range, high30_slider_range, selected_themes,
                                open_positions_filter, ath_drop_enabled, ath_drop_days, ath_drop_std_pct,
                                ath_drop_override_pct, ath_drop_bypass_count,
                                pc1_days, pc1_min_pct, pc2_days, pc2_min_pct,
                                trend_d, trend_w, trend_m, min_vol_ratio, _reload_status):
        """
        Filters the ticker dropdown options based on various filter sliders.
        """
        ticker_info = state['ticker_info']
        close_prices_df = state['close_prices_df']
        open_positions = state['open_positions']
        if not ticker_info:
            return []

        ath_min, ath_max = ath_slider_range
        sma30_min, sma30_max = sma30_slider_range
        ema30_min, ema30_max = ema30_slider_range
        sma90_min, sma90_max = sma90_slider_range
        sma20_30_min, sma20_30_max = sma20_30_slider_range
        ema32_30_min, ema32_30_max = ema32_30_slider_range
        high30_min, high30_max = high30_slider_range

        # Initial filtering based on standard sliders
        filtered_tickers = [
            t for t in ticker_info
            if (ath_min <= t['pct_diff'] <= ath_max and
                sma30_min <= t['days_above_sma30'] <= sma30_max and
                ema30_min <= t['days_above_ema30'] <= ema30_max and
                sma90_min <= t['days_above_sma90'] <= sma90_max and
                sma20_30_min <= t['days_above_sma20_30'] <= sma20_30_max and
                ema32_30_min <= t['days_above_ema32_30'] <= ema32_30_max and
                high30_min <= t['days_above_high30'] <= high30_max)
        ]

        # Apply D/W/M trend filters (tickers with unknown trend drop out as
        # soon as any trend filter is set).
        for tf, wanted in (("D", trend_d), ("W", trend_w), ("M", trend_m)):
            if wanted and wanted != 'any':
                filtered_tickers = [t for t in filtered_tickers
                                    if t.get('trend') and t['trend'][tf] == wanted]

        # Apply volume filter: last volume >= N x its 20-day average.
        if min_vol_ratio:
            filtered_tickers = [t for t in filtered_tickers
                                if t.get('vol_ratio') is not None and t['vol_ratio'] >= min_vol_ratio]

        # Apply theme filter
        if selected_themes:
            filtered_tickers = [t for t in filtered_tickers if t.get('theme') in selected_themes]

        # Apply open positions filter
        if 'enabled' in open_positions_filter:
            filtered_tickers = [t for t in filtered_tickers if t['value'] not in open_positions]

        # Function to apply Price Change Filter
        def apply_pc_filter(current_filtered, days, min_pct):
            if days is None or min_pct is None:
                return current_filtered
            
            # Determine reference dates
            end_date = close_prices_df['Date'].max()
            start_date = end_date - pd.to_timedelta(days, unit='D')
            
            # Filter close_prices_df for current candidate tickers
            candidate_tickers_set = set(t['value'] for t in current_filtered)
            if not candidate_tickers_set:
                return []
                
            relevant_df = close_prices_df[close_prices_df['Ticker'].isin(candidate_tickers_set)]
            
            # Get latest prices (last available for each ticker)
            curr_prices = relevant_df.sort_values('Date').groupby('Ticker')['Price'].last()
            
            # Get past prices (last available on or before start_date)
            past_prices_df = relevant_df[relevant_df['Date'] <= start_date]
            past_prices = past_prices_df.sort_values('Date').groupby('Ticker')['Price'].last()
            
            # Calculate % change
            common_tickers = curr_prices.index.intersection(past_prices.index)
            pct_changes = (curr_prices.loc[common_tickers] - past_prices.loc[common_tickers]) / past_prices.loc[common_tickers] * 100
            
            # Filter
            valid_tickers = pct_changes[pct_changes >= min_pct].index
            valid_tickers_set = set(valid_tickers)
            return [t for t in current_filtered if t['value'] in valid_tickers_set]

        # Apply Price Change Filter 1
        filtered_tickers = apply_pc_filter(filtered_tickers, pc1_days, pc1_min_pct)
        # Apply Price Change Filter 2
        filtered_tickers = apply_pc_filter(filtered_tickers, pc2_days, pc2_min_pct)

        # Apply dynamic ATH drop filter if enabled
        if 'enabled' in ath_drop_enabled:
            tickers_to_keep = []
            allowed_overrides = ath_drop_bypass_count or 0

            for ticker_data in filtered_tickers:
                ticker_val = ticker_data['value']
                ticker_df = close_prices_df[close_prices_df['Ticker'] == ticker_val]

                if len(ticker_df) < ath_drop_days:
                    continue

                # Calculate rolling ATH and pct drop
                rolling_ath = ticker_df['Price'].rolling(window=ath_drop_days, min_periods=1).max()
                pct_drop = (rolling_ath - ticker_df['Price']) / rolling_ath.replace(0, 1)
                
                recent_drops = pct_drop.tail(ath_drop_days)

                # Check for hard violations (drops > override_drop_pct)
                hard_violations = (recent_drops > (ath_drop_override_pct / 100)).sum()
                if hard_violations > 0:
                    continue

                # Count soft violations (std_drop_pct < drop <= override_drop_pct)
                soft_violations = ((recent_drops > (ath_drop_std_pct / 100)) & (recent_drops <= (ath_drop_override_pct / 100))).sum()
                
                if soft_violations <= allowed_overrides:
                    tickers_to_keep.append(ticker_data)
            
            filtered_tickers = tickers_to_keep

        return [{'label': t['label'], 'value': t['value']} for t in filtered_tickers]

    @app.callback(
        Output('ticker-dropdown', 'value'),
        Input('select-all-button', 'n_clicks'),
        State('ticker-dropdown', 'options'),
        prevent_initial_call=True
    )
    def select_all_filtered_tickers(n_clicks, available_options):
        """
        Selects all tickers currently visible in the dropdown when the button is clicked.
        """
        if n_clicks and available_options:
            return [option['value'] for option in available_options]
        return dash.no_update # pragma: no cover

    @app.callback(
        [Output('price-performance-graph', 'figure'),
         Output('date-range-count', 'children')],
        [
            Input('ticker-dropdown', 'value'),
            Input('metric-checklist', 'value'),
            Input('days-slider', 'value'),
            Input('indicator-checklist', 'value'),
            Input('interval-radio', 'value'),
        ],
        [State('hidden-traces-store', 'data')]
    )
    def update_graph(selected_tickers, selected_metrics, date_range, selected_indicators,
                     interval, hidden_tickers):
        """
        Updates the main performance graph based on user selections and returns the count of days.
        Daily or weekly candles (interval), indicators computed at that interval.
        """
        if not selected_tickers or not selected_metrics or not date_range:
            fig = go.Figure()
            fig.update_layout(
                title="Please select tickers and price types to view the graph",
                xaxis={'visible': False},
                yaxis={'visible': False},
                annotations=[{'text': 'No data selected', 'xref': 'paper', 'yref': 'paper', 'showarrow': False, 'font': {'size': 20, 'color': '#888'}}]
            )
            return fig, "No days selected"

        df_melted = state['df_melted']
        min_date = df_melted['Date'].min()
        start_idx, end_idx = date_range
        start_date = min_date + pd.to_timedelta(start_idx, unit='D')
        end_date = min_date + pd.to_timedelta(end_idx, unit='D')
        
        # Calculate number of days selected
        selected_days_count = (end_date - start_date).days + 1
        count_text = f"Selected: {selected_days_count} days"

        # Per-ticker OHLC at the displayed interval; the price lines and the
        # indicators are both built from it, so weekly mode stays consistent.
        ohlc_by_ticker = {}
        for ticker in selected_tickers:
            ohlc = _wide_ohlc(state['df_wide'], ticker)
            if interval == 'W':
                ohlc = resample_ohlc(ohlc, 'W')
            if not ohlc.empty:
                ohlc_by_ticker[ticker] = ohlc

        rows = [_price_rows(o, t, selected_metrics) for t, o in ohlc_by_ticker.items()]
        filtered_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
            columns=['Date', 'Metric', 'Price', 'Ticker'])
        filtered_df = filtered_df[(filtered_df['Date'] >= start_date)
                                  & (filtered_df['Date'] <= end_date)].copy()
        meta = state.get('ticker_meta')
        if meta is not None and not filtered_df.empty:
            filtered_df = filtered_df.join(meta, on='Ticker')

        if filtered_df.empty:
            fig = go.Figure()
            fig.update_layout(title=f"No data available for selected criteria in the range {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.")
            return fig, count_text

        # Normalize percent change per (Ticker, Metric)
        base_prices = filtered_df.groupby(['Ticker', 'Metric'])['Price'].transform('first')
        # Avoid division by zero
        safe_base = base_prices.replace(0, 1)
        filtered_df['Normalized Price (%)'] = (filtered_df['Price'] / safe_base - 1.0) * 100.0

        # Define hover data
        hover_data_config = {'Price': ':.2f'}
        for col in ('Theme', 'Country/Region'):
            if col in filtered_df.columns:
                hover_data_config[col] = True

        fig = px.line(
            filtered_df.sort_values(['Ticker', 'Metric', 'Date']),
            x='Date',
            y='Normalized Price (%)',
            color='Ticker',
            line_dash='Metric',
            title=(f'Price Performance{" (weekly)" if interval == "W" else ""} '
                   f'({start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")})'),
            labels={'Normalized Price (%)': 'Price Change (%)'},
            hover_data=hover_data_config
        )

        fig.update_layout(
            template='plotly_white',
            legend_title_text='Legend',
            yaxis_ticksuffix="%",
            xaxis_title="Date",
            title_font_size=24,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        # Indicator overlays (same registry app/output/positions_chart.py uses -
        # see services/indicators.py). Rebased onto this chart's normalized
        # '% change from day 0' scale in _indicator_traces().
        if selected_indicators:
            for ticker in selected_tickers:
                close_rows = filtered_df[(filtered_df['Ticker'] == ticker)
                                         & (filtered_df['Metric'] == 'Close')]
                if close_rows.empty:
                    continue
                base = float(close_rows.sort_values('Date')['Price'].iloc[0]) or 1.0
                for tr in _indicator_traces(ticker, ohlc_by_ticker.get(ticker), selected_indicators,
                                            base, start_date, end_date,
                                            cache=state.setdefault('indicator_cache', {}),
                                            cache_key=(ticker, interval)):
                    fig.add_trace(tr)
            _stack_panes(fig)

        # Re-apply hidden state (matches on the ticker name itself, or on the
        # leading "<TICKER> " an indicator trace's name carries, so hiding a
        # ticker also hides its indicator overlays).
        hidden_set = set(hidden_tickers or [])
        if hidden_set:
            fig.for_each_trace(
                lambda t: t.update(visible='legendonly')
                if (t.name in hidden_set or (t.name or '').split(' ', 1)[0] in hidden_set)
                else None
            )

        return fig, count_text

    @app.callback(
        Output('trend-badges', 'children'),
        [Input('ticker-dropdown', 'value'),
         Input('reload-status', 'children')],
    )
    def update_trend_badges(selected_tickers, _reload_status):
        """D/W/M trend chips for every selected ticker (from _load_data's trend_summary)."""
        info = {t['value']: t for t in state['ticker_info']}
        return [trend_badge(t, info.get(t, {}).get('trend')) for t in (selected_tickers or [])]

    @app.callback(
        Output('price-performance-graph', 'figure', allow_duplicate=True),
        Output('hidden-traces-store', 'data'),
        Input('price-performance-graph', 'clickData'),
        State('price-performance-graph', 'figure'),
        State('hidden-traces-store', 'data'),
        prevent_initial_call=True
    )
    def toggle_visibility_on_click(clickData, figure, hidden_tickers):
        """
        Toggles the visibility of a trace when it is clicked on the graph.
        """
        if not clickData:
            return dash.no_update, dash.no_update

        hidden_set = set(hidden_tickers or [])

        curve_number = clickData['points'][0]['curveNumber']
        clicked_ticker = figure['data'][curve_number]['name']

        fig = go.Figure(figure)

        # Toggle hidden/visible
        if clicked_ticker in hidden_set:
            # Make visible: remove from hidden list
            hidden_set.remove(clicked_ticker)
            trace_visible_state = True
        else:
            # Hide: add to hidden list
            hidden_set.add(clicked_ticker)
            trace_visible_state = 'legendonly'

        fig.data[curve_number].visible = trace_visible_state

        return fig, list(hidden_set)

    @app.callback(
        [Output('ticker-dropdown', 'options', allow_duplicate=True),
         Output('ticker-dropdown', 'value', allow_duplicate=True),
         Output('theme-filter-dropdown', 'options', allow_duplicate=True),
         Output('days-slider', 'min', allow_duplicate=True),
         Output('days-slider', 'max', allow_duplicate=True),
         Output('days-slider', 'value', allow_duplicate=True),
         Output('days-slider', 'marks', allow_duplicate=True),
         Output('date-picker', 'min_date_allowed'),
         Output('date-picker', 'max_date_allowed'),
         Output('reload-status', 'children')],
        [Input('reload-data-button', 'n_clicks'),
         Input('initial-load-trigger', 'n_intervals')],
        [State('ticker-dropdown', 'value')],
        prevent_initial_call=True
    )
    def reload_data(n_clicks, n_intervals, current_selection):
        """Re-reads the CSV/DB from disk and refreshes the in-memory dataset used by all other callbacks."""
        new_data = _load_data(procedure_choice)
        if new_data is None:
            return (dash.no_update,) * 9 + (
                f"Reload failed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - check server logs",
            )

        state.clear()
        state.update(new_data)

        ticker_info = state['ticker_info']
        df_melted = state['df_melted']
        max_days = state['max_days']

        options = [{'label': t['label'], 'value': t['value']} for t in ticker_info]
        valid_values = {t['value'] for t in ticker_info}
        new_selection = [v for v in (current_selection or []) if v in valid_values]
        if not new_selection:
            new_selection = [v for v in initial_dropdown_value if v in valid_values]

        theme_options = [{'label': theme, 'value': theme} for theme in state['all_themes']]

        marks = {
            0: df_melted['Date'].min().strftime('%Y-%m-%d'),
            max_days - 1: df_melted['Date'].max().strftime('%Y-%m-%d'),
        }
        slider_value = [max(0, max_days - 30), max_days - 1]
        status = f"Loaded at {state['loaded_at'].strftime('%Y-%m-%d %H:%M:%S')}"

        return (options, new_selection, theme_options, 0, max_days - 1, slider_value, marks,
                df_melted['Date'].min().date(), df_melted['Date'].max().date(), status)

    preset_ids = [f"range-{n}" for n in RANGE_PRESETS]

    @app.callback(
        [Output('days-slider', 'value', allow_duplicate=True),
         Output('date-picker', 'start_date'),
         Output('date-picker', 'end_date')]
        + [Output(i, 'className') for i in preset_ids],
        [Input(i, 'n_clicks') for i in preset_ids]
        + [Input('date-picker', 'start_date'),
           Input('date-picker', 'end_date'),
           Input('days-slider', 'value')],
        prevent_initial_call=True,
    )
    def sync_date_range(*args):
        """Keeps the slider, the 30/90/180/360d presets and the calendar picker
        in step. All three live in one callback because each is both an input
        and an output of the others (Dash only allows that circularity within
        a single callback). Slider values are day offsets from the first
        loaded date; a preset means 'the last N days up to the newest date'."""
        start_date, end_date, slider_value = args[len(preset_ids):]
        min_date = state['df_melted']['Date'].min()
        max_idx = state['max_days'] - 1
        triggered = dash.callback_context.triggered[0]['prop_id'].split('.')[0] \
            if dash.callback_context.triggered else ''

        if triggered in preset_ids:
            n = RANGE_PRESETS[preset_ids.index(triggered)]
            value = [max(0, max_idx - n + 1), max_idx]
        elif triggered == 'date-picker':
            if not start_date or not end_date:
                return (dash.no_update,) * (3 + len(preset_ids))
            to_idx = lambda d: min(max((pd.Timestamp(d) - min_date).days, 0), max_idx)
            value = sorted([to_idx(start_date), to_idx(end_date)])
        else:
            value = slider_value or [max(0, max_idx - 29), max_idx]

        classes = ["range-btn active" if value == [max(0, max_idx - n + 1), max_idx] else "range-btn"
                   for n in RANGE_PRESETS]
        return ([value,
                 (min_date + pd.Timedelta(days=value[0])).date(),
                 (min_date + pd.Timedelta(days=value[1])).date()]
                + classes)

    # Start the web server
    if not server:
        app.run(debug=True, use_reloader=False)

    return app


# If you want to be able to run this file directly:
if __name__ == "__main__":
    # Example default: procedure_choice and a default selection list
    # Adjust these as needed when integrating with your main()
    graph_start(procedure_choice="13", def_filter_graph_list=['AVGO', 'CRWD'])
