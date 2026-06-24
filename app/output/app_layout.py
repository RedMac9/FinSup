from dash import Dash, dcc, html
import plotly.graph_objects as go


def make_placeholder_figure():
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=["Feb", "Mar", "Apr", "May"],
            y=[-2, 4, 12, 18],
            mode="lines",
            name="AVGO",
            line=dict(color="#0b57d0", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=["Feb", "Mar", "Apr", "May"],
            y=[-3, 2, 6, 9],
            mode="lines",
            name="CRWD",
            line=dict(color="#1a73e8", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=["Feb", "Mar", "Apr", "May"],
            y=[-1, 1, 10, 21],
            mode="lines",
            name="NVDA",
            line=dict(color="#137333", width=3),
        )
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=24, r=24, t=24, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#eef2f7",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis_title="Price Change (%)",
        xaxis_title="Date",
    )
    return fig


def build_app():
    app = Dash(__name__)

    app.layout = html.Div(
        className="app-shell",
        children=[
            html.Nav(
                className="nav-rail",
                children=[
                    html.Button("+", className="rail-fab", id="rail-fab"),
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
            html.Aside(
                className="filter-drawer",
                children=[
                    html.Div(
                        className="drawer-header",
                        children=[
                            html.H1("Ticker filters", className="drawer-title"),
                            html.P(
                                "Implementacyjny layout pod Dash: rail + drawer + top app bar + content region.",
                                className="drawer-subtitle",
                            ),
                            dcc.Input(
                                id="filter-search-input",
                                type="text",
                                value="",
                                placeholder="Search filter or ticker",
                                className="search-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="drawer-section",
                        children=[
                            html.Div("Core filters", className="section-label"),
                            html.Div(
                                className="m3-card stack-lg",
                                children=[
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="filter-row",
                                                children=[
                                                    html.Label("% from 30-Day ATH", className="field-label"),
                                                    html.Span("-50% → 0%", className="field-value"),
                                                ],
                                            ),
                                            dcc.RangeSlider(
                                                id="ath-filter-slider",
                                                min=-100,
                                                max=0,
                                                step=1,
                                                value=[-50, 0],
                                                marks={i: f"{i}%" for i in range(-100, 1, 20)},
                                                tooltip={"placement": "bottom", "always_visible": False},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="filter-row",
                                                children=[
                                                    html.Label("Days Close Above SMA10 (30d)", className="field-label"),
                                                    html.Span("0 → 30", className="field-value"),
                                                ],
                                            ),
                                            dcc.RangeSlider(
                                                id="sma-filter-slider",
                                                min=0,
                                                max=30,
                                                step=1,
                                                value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="filter-row",
                                                children=[
                                                    html.Label("Days Close Above EMA10 (30d)", className="field-label"),
                                                    html.Span("0 → 30", className="field-value"),
                                                ],
                                            ),
                                            dcc.RangeSlider(
                                                id="ema-filter-slider",
                                                min=0,
                                                max=30,
                                                step=1,
                                                value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="filter-row",
                                                children=[
                                                    html.Label("Days Close Above SMA10 (90d)", className="field-label"),
                                                    html.Span("0 → 90", className="field-value"),
                                                ],
                                            ),
                                            dcc.RangeSlider(
                                                id="sma90-filter-slider",
                                                min=0,
                                                max=90,
                                                step=1,
                                                value=[0, 90],
                                                marks={i: str(i) for i in range(0, 91, 30)},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="drawer-section",
                        children=[
                            html.Div("Advanced filtering", className="section-label"),
                            html.Div(
                                className="m3-card stack-lg",
                                children=[
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="filter-row",
                                                children=[
                                                    html.Label("Days Close Above SMA20 / EMA32 (30d)", className="field-label"),
                                                    html.Span("0 → 30", className="field-value"),
                                                ],
                                            ),
                                            dcc.RangeSlider(
                                                id="sma20-30-filter-slider",
                                                min=0,
                                                max=30,
                                                step=1,
                                                value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                            dcc.RangeSlider(
                                                id="ema32-30-filter-slider",
                                                min=0,
                                                max=30,
                                                step=1,
                                                value=[0, 30],
                                                marks={i: str(i) for i in range(0, 31, 10)},
                                            ),
                                        ],
                                    ),
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
                                    html.Div(
                                        className="filter-item",
                                        children=[
                                            html.Div(
                                                className="toggle-row",
                                                children=[
                                                    html.Div(
                                                        children=[
                                                            html.Div("ATH Drop Filter", className="field-label"),
                                                            html.Div("90d / standard 6.5% / override 12%", className="support-text"),
                                                        ]
                                                    ),
                                                    dcc.Checklist(
                                                        id="ath-drop-enable",
                                                        options=[{"label": "Enabled", "value": "enabled"}],
                                                        value=["enabled"],
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
                                                            dcc.Input(id="ath-drop-std-pct-slider", type="number", value=6.5, min=0, className="m3-input"),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="field-surface",
                                                        children=[
                                                            html.Label("Override drop %", className="mini-label"),
                                                            dcc.Input(id="ath-drop-override-pct-slider", type="number", value=12.0, min=0, className="m3-input"),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            dcc.Checklist(
                                                id="open-positions-filter",
                                                options=[{"label": "Disable open positions", "value": "enabled"}],
                                                value=["enabled"],
                                                className="toggle-checklist secondary-toggle",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="drawer-section",
                        children=[
                            html.Div("Ticker selection", className="section-label"),
                            html.Div(
                                className="m3-card stack-md",
                                children=[
                                    dcc.Dropdown(
                                        id="ticker-dropdown",
                                        options=[
                                            {"label": "AVGO", "value": "AVGO"},
                                            {"label": "CRWD", "value": "CRWD"},
                                            {"label": "NVDA", "value": "NVDA"},
                                            {"label": "MSFT", "value": "MSFT"},
                                        ],
                                        value=["AVGO", "CRWD"],
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
            html.Main(
                className="main-content",
                children=[
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
                                        options=[{"label": x, "value": x} for x in ["Close", "Open", "High", "Low"]],
                                        value=["Close"],
                                        multi=True,
                                        className="compact-dropdown",
                                    ),
                                    dcc.Input(id="days-slider-proxy", type="number", value=90, min=1, className="compact-input"),
                                    html.Button("Apply preset", id="apply-preset", className="btn-outline"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="page-scroll",
                        children=[
                            html.Section(
                                className="hero-grid",
                                children=[
                                    html.Div(
                                        className="hero-card",
                                        children=[
                                            html.Div("Ultra Material 3 • Dash-ready", className="hero-chip"),
                                            html.H3("Gotowy layout do przepisania z mockupu na komponenty Dash", className="hero-title"),
                                            html.P(
                                                "Ten plik nie jest tylko makietą wizualną: używa realnych komponentów dcc/html, ma nazwy id zgodne z istniejącą logiką filtrów i pozwala łatwo podpiąć callbacki do obecnej aplikacji.",
                                                className="hero-copy",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="summary-column",
                                        children=[
                                            html.Div(className="summary-card", children=[html.Div("Visible tickers", className="summary-label"), html.Div("24", className="summary-value"), html.Div("po update_dropdown_options", className="summary-meta")]),
                                            html.Div(className="summary-card", children=[html.Div("Primary color", className="summary-label"), html.Div("Google Blue", className="summary-value"), html.Div("#0b57d0", className="summary-meta")]),
                                            html.Div(className="summary-card", children=[html.Div("State model", className="summary-label"), html.Div("Rail + Drawer", className="summary-value"), html.Div("łatwy do utrzymania w Dash", className="summary-meta")]),
                                        ],
                                    ),
                                ],
                            ),
                            html.Section(
                                className="metric-grid",
                                children=[
                                    html.Div(className="metric-card", children=[html.Div("Selected tickers", className="metric-label"), html.Div("4", className="metric-value"), html.Div("AVGO, CRWD, NVDA, MSFT", className="metric-meta")]),
                                    html.Div(className="metric-card", children=[html.Div("Avg from ATH", className="metric-label"), html.Div("-5.0%", className="metric-value"), html.Div("Close vs ATH30", className="metric-meta")]),
                                    html.Div(className="metric-card", children=[html.Div("Best 30d move", className="metric-label"), html.Div("+18.4%", className="metric-value positive"), html.Div("NVDA", className="metric-meta")]),
                                    html.Div(className="metric-card", children=[html.Div("Worst 30d move", className="metric-label"), html.Div("-3.2%", className="metric-value negative"), html.Div("MSFT", className="metric-meta")]),
                                ],
                            ),
                            html.Section(
                                className="analytics-grid",
                                children=[
                                    html.Div(
                                        className="panel-card",
                                        children=[
                                            html.Div(
                                                className="panel-head",
                                                children=[
                                                    html.Div(children=[html.H3("Price performance", className="panel-title"), html.P("Podmień placeholder na istniejący figure w update_graph().", className="panel-copy")]),
                                                    html.Div("Live selection", className="state-chip"),
                                                ],
                                            ),
                                            dcc.Graph(id="price-performance-graph", figure=make_placeholder_figure(), config={"displayModeBar": False}, className="graph-frame"),
                                        ],
                                    ),
                                    html.Div(
                                        className="panel-card",
                                        children=[
                                            html.Div(
                                                className="panel-head",
                                                children=[
                                                    html.Div(children=[html.H3("Filter state", className="panel-title"), html.P("Panel pomocniczy pod live summaries albo debug callbacków.", className="panel-copy")]),
                                                    html.Div("Synced", className="state-chip"),
                                                ],
                                            ),
                                            html.Div(
                                                className="state-list",
                                                children=[
                                                    html.Div(className="state-row", children=[html.Div([html.Strong("ATH 30d"), html.Div("-50% → 0%", className="state-sub")]), html.Strong("Active")]),
                                                    html.Div(className="state-row", children=[html.Div([html.Strong("SMA10 / EMA10"), html.Div("0→30 / 0→30", className="state-sub")]), html.Strong("Passed")]),
                                                    html.Div(className="state-row", children=[html.Div([html.Strong("SMA90 / SMA20 / EMA32"), html.Div("0→90 / 0→30 / 0→30", className="state-sub")]), html.Strong("Passed")]),
                                                    html.Div(className="state-row", children=[html.Div([html.Strong("ATH Drop logic"), html.Div("90 / 6.5 / 12 / 0", className="state-sub")]), html.Strong("On")]),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Section(
                                className="panel-card",
                                children=[
                                    html.Div(
                                        className="panel-head",
                                        children=[
                                            html.Div(children=[html.H3("Implementation notes", className="panel-title"), html.P("Ten blok możesz później zamienić na DataTable albo dodatkowy summary panel.", className="panel-copy")]),
                                            html.Div("Dash-ready", className="state-chip"),
                                        ],
                                    ),
                                    html.Ul(
                                        className="notes-list",
                                        children=[
                                            html.Li("Zachowano kluczowe id filtrów zgodne z graph.py: ath-filter-slider, sma-filter-slider, ema-filter-slider, sma90-filter-slider, sma20-30-filter-slider, ema32-30-filter-slider, ticker-dropdown i price-performance-graph."),
                                            html.Li("Layout rozdziela strukturę na: rail, drawer, top app bar i page content, więc możesz przenieść callbacki bez mieszania ich z warstwą CSS."),
                                            html.Li("CSS jest zewnętrzny, zgodnie z praktyką Dash assets/, a Dash wspiera dołączanie własnych zasobów i stylów przez katalog assets oraz layout z dash.html komponentów."),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return app


app = build_app()


if __name__ == "__main__":
    app.run(debug=True)
