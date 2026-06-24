import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from tickers_lists.ticker_groups import payloadPROD_db


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


def graph_start(procedure_choice, def_filter_graph_list, server=None):
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

    # Get unique tickers and available metrics for the controls
    ALL_METRICS = ['Close', 'Open', 'High', 'Low']
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
    else:
        latest_theme = pd.Series(dtype='object')

    # Create a list of dictionaries containing ticker info for the dropdown
    ticker_info = []
    for ticker, pct_diff in latest_pct_diff.items():
        days_above_sma30 = latest_days_above_sma30.get(ticker, 0)
        days_above_sma90 = latest_days_above_sma90.get(ticker, 0)
        days_above_ema30 = latest_days_above_ema30.get(ticker, 0)
        days_above_sma20_30 = latest_days_above_sma20_30.get(ticker, 0)
        days_above_ema32_30 = latest_days_above_ema32_30.get(ticker, 0)
        days_above_high30 = latest_days_above_high30.get(ticker, 0)

        label = (
            f"{ticker} (ATH: {pct_diff:.1f}%, "
            f"EMA30: {days_above_ema30:.0f}d, "
            f"SMA30: {days_above_sma30:.0f}d, "
            f"SMA90: {days_above_sma90:.0f}d, "
            f"SMA20-30d: {days_above_sma20_30:.0f}d, "
            f"EMA32-30d: {days_above_ema32_30:.0f}d, "
            f"High30: {days_above_high30:.0f}d)"
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
            'days_above_high30': float(days_above_high30) if pd.notna(days_above_high30) else 0.0
        }
        if procedure_choice == "13":
            info['theme'] = latest_theme.get(ticker, 'N/A')
        ticker_info.append(info)


    # Sort ticker_info by pct_diff descending
    ticker_info = sorted(ticker_info, key=lambda x: x['pct_diff'], reverse=True)

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
                options=[{'label': theme, 'value': theme} for theme in all_themes],
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
            # Rail
            html.Nav(
                className="nav-rail",
                children=[
                    html.Button("≡", className="rail-fab", id="rail-toggle"),
                    html.Div(
                        className="rail-links",
                        children=[
                            html.Button("Dashboard", className="rail-link active", id="rail-dashboard"),
                            html.Button("Filters", className="rail-link", id="rail-filters"),
                            html.Button("Charts", className="rail-link", id="rail-charts"),
                            html.Button("Universe", className="rail-link", id="rail-universe"),
                        ],
                    ),
                ],
            ),
            # Drawer
            html.Aside(
                className="filter-drawer",
                id="filter-drawer",
                children=[
                    html.Div(
                        className="drawer-header",
                        children=[
                            html.H1("Ticker filters", className="drawer-title"),
                            html.P(
                                "M3 Material Layout with Rail and Drawer.",
                                className="drawer-subtitle",
                            ),
                        ],
                    ),
                    # Core Filters Section
                    html.Div(
                        className="drawer-section",
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
                        children=[
                            html.Div("Ticker selection", className="section-label"),
                            html.Div(
                                className="m3-card stack-md",
                                children=[
                                    theme_filter_layout,
                                    dcc.Dropdown(
                                        id="ticker-dropdown",
                                        options=[{'label': t['label'], 'value': t['value']} for t in ticker_info],
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
                        children=[
                            html.Div(
                                className="title-block",
                                children=[
                                    html.Div("Stock Ticker Performance Analysis", className="top-caption"),
                                    html.H2("Dashboard", className="top-title"),
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
                                    html.Div([
                                        html.Label("Date Range:", className="mini-label"),
                                        dcc.RangeSlider(
                                            id="days-slider",
                                            min=0,
                                            max=max_days - 1,
                                            value=[max(0, max_days - 30), max_days - 1],
                                            step=1,
                                            marks={
                                                0: (df_melted['Date'].min()).strftime('%Y-%m-%d'),
                                                max_days - 1: (df_melted['Date'].max()).strftime('%Y-%m-%d')
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
         Output('drawer-state', 'data')],
        [Input('rail-toggle', 'n_clicks')],
        [State('drawer-state', 'data')]
    )
    def toggle_drawer(n_clicks, state):
        visible = state['visible']
        if n_clicks:
            visible = not visible
        
        shell_style = {
            'gridTemplateColumns': f"96px {'392px' if visible else '0px'} minmax(0, 1fr)",
            'transition': 'grid-template-columns 0.3s ease',
        }
        
        drawer_style = {
            'display': 'block', # Keep in grid to maintain column mapping
            'visibility': 'visible' if visible else 'hidden',
            'overflow': 'hidden',
            'width': '392px' if visible else '0px',
            'transition': 'width 0.3s, visibility 0.3s',
        }
        
        return shell_style, drawer_style, {'visible': visible}

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
            Input('price-change-pct-input-2', 'value')
        ]
    )
    def update_dropdown_options(ath_slider_range, sma30_slider_range, ema30_slider_range, sma90_slider_range,
                                sma20_30_slider_range, ema32_30_slider_range, high30_slider_range, selected_themes,
                                open_positions_filter, ath_drop_enabled, ath_drop_days, ath_drop_std_pct,
                                ath_drop_override_pct, ath_drop_bypass_count,
                                pc1_days, pc1_min_pct, pc2_days, pc2_min_pct):
        """
        Filters the ticker dropdown options based on various filter sliders.
        """
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
            Input('days-slider', 'value')
        ],
        [State('hidden-traces-store', 'data')]
    )
    def update_graph(selected_tickers, selected_metrics, date_range, hidden_tickers):
        """
        Updates the main performance graph based on user selections and returns the count of days.
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

        min_date = df_melted['Date'].min()
        start_idx, end_idx = date_range
        start_date = min_date + pd.to_timedelta(start_idx, unit='D')
        end_date = min_date + pd.to_timedelta(end_idx, unit='D')
        
        # Calculate number of days selected
        selected_days_count = (end_date - start_date).days + 1
        count_text = f"Selected: {selected_days_count} days"

        # Base filtering
        mask = (
            (df_melted['Date'] >= start_date) &
            (df_melted['Date'] <= end_date) &
            (df_melted['Ticker'].isin(selected_tickers)) &
            (df_melted['Metric'].isin(selected_metrics))
        )
        filtered_df = df_melted[mask].copy()

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
        if procedure_choice == "13":
            hover_data_config['Theme'] = True
            hover_data_config['Country/Region'] = True

        fig = px.line(
            filtered_df,
            x='Date',
            y='Normalized Price (%)',
            color='Ticker',
            line_dash='Metric',
            title=f'Price Performance ({start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")})',
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

        # Re-apply hidden state
        hidden_set = set(hidden_tickers or [])
        if hidden_set:
            fig.for_each_trace(
                lambda t: t.update(visible='legendonly') if t.name in hidden_set else None
            )

        return fig, count_text

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

    # Start the web server
    if not server:
        app.run(debug=True, use_reloader=False)

    return app


# If you want to be able to run this file directly:
if __name__ == "__main__":
    # Example default: procedure_choice and a default selection list
    # Adjust these as needed when integrating with your main()
    graph_start(procedure_choice="13", def_filter_graph_list=['AVGO', 'CRWD'])
