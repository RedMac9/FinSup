"""Steady-uptrend screener: stocks rising along a log-linear trend without sharp
drops. Upside breakouts above the trend line are never penalized - only the
downside (residuals below the line, drawdowns, down days) counts against a
ticker.

Metrics are computed for every ticker at once on the Date x Ticker close matrix
(NaN = no quote that day), so the screener stays fast for the US universe.
"""
import numpy as np
import pandas as pd

# Every threshold of the screener in one place. graph.py uses these as the
# initial values of the drawer inputs, so changing a default here changes the UI.
# Defaults target a ~3-month holding horizon: a 6-month trend (where momentum
# persists best) that is smooth (few sharp drops) and recently accelerating.
STEADY_TREND_PARAMS = {
    'period_days': 180,          # calendar-day lookback of the regression
    'min_growth_pct': 5.0,       # trend growth per GROWTH_HORIZON_DAYS (~22%/yr; slope > 0 always required)
    'max_downside_dev_pct': 4.5, # RMS of the negative log residuals, in %
    'max_drawdown_pct': 20.0,    # deepest peak-to-trough fall inside the period
    'max_daily_drop_pct': 7.0,   # worst single-day close-to-close fall (use ~5 for ETFs)
    'min_updown_ratio': 0.0,     # upside / downside deviation (0 = no limit)
    'min_coverage_pct': 90.0,    # quotes needed, % of the period's trading days
    'momentum_days': 60,         # recent window for the momentum flag ...
    'momentum_factor': 1.3,      # ... flagged if its growth > factor x trend-implied
}

# Trend growth is expressed over this many calendar days (independent of the
# period), matching the 3-month horizon and keeping steep slopes from being
# blown up by annual compounding in the score.
GROWTH_HORIZON_DAYS = 90

# Separate trend regressions feeding the combined score: window (calendar days)
# -> weight. The 1-year trend is weight 0: computed for the table's "Growth 1y %"
# column but left out of the score. A window without enough quotes
# (min_coverage_pct) is left out and the remaining weights are rescaled.
SCORE_GROWTH_WINDOWS = {30: 0.5, 90: 0.5, 365: 0.0}

TRADING_DAYS_PER_YEAR = 252
SCORE_RATIO_CAP = 10.0   # stops a near-zero downside deviation from dominating the score

# Display columns (name -> metric key); percentages are already in %.
STEADY_TREND_COLUMNS = {
    'Ticker': 'ticker',
    'Pass': 'passes',
    'Fails': 'fails',
    'Score': 'score',
    'Combined growth %/90d': 'combined_growth_pct',
    'Growth 30d %': 'growth_30d_pct',
    'Growth 90d %': 'growth_90d_pct',
    'Growth 1y %': 'growth_365d_pct',
    'Period trend %/90d': 'trend_growth_pct',
    'Downside dev %': 'downside_dev_pct',
    'Max below trend %': 'max_below_trend_pct',
    'Max drawdown %': 'max_drawdown_pct',
    'Max daily drop %': 'max_daily_drop_pct',
    'Up/Down ratio': 'updown_ratio',
    'Sortino': 'sortino',
    'R²': 'r2',
    'Momentum': 'momentum',
    'Points': 'points',
}

# Hover help for the drawer inputs (STEADY_TREND_PARAMS keys) and the table
# columns (STEADY_TREND_COLUMNS names).
STEADY_TREND_PARAM_HELP = {
    'period_days': "Calendar-day lookback of the screening regression (log close vs. time). "
                   "All pass/fail criteria are measured over this period.",
    'min_growth_pct': "Minimum growth of the period's trend line, expressed per 90 days "
                      "(5 %/90d is about 22 %/year). The trend must also slope upward.",
    'max_downside_dev_pct': "Maximum RMS of the closes BELOW the trend line (log residuals, %). "
                            "Moves above the line never count against a ticker.",
    'max_drawdown_pct': "Maximum peak-to-trough fall of the close inside the period.",
    'max_daily_drop_pct': "Maximum single-day close-to-close fall inside the period (use ~5 for ETFs).",
    'min_updown_ratio': "Minimum upside / downside deviation around the trend line. 0 = no limit; "
                        ">1 means the price spends more distance above the line than below it.",
    'min_coverage_pct': "Minimum share of the period's trading days that must have a quote. "
                        "Filters out recent listings and tickers with gaps.",
    'momentum_days': "Recent window for the 🚀 momentum flag.",
    'momentum_factor': "🚀 momentum: growth over the momentum window is greater than this factor × "
                       "the growth the trend line implies for the same window.",
}

STEADY_TREND_COLUMN_HELP = {
    'Ticker': "Ticker symbol.",
    'Pass': "✓ = meets every steady-uptrend criterion; ✗ = fails at least one (see Fails).",
    'Fails': "Criteria the ticker fails: history (coverage), growth, downside, drawdown, "
             "daily drop, up/down.",
    'Score': "Ranking: combined growth × (1 + ln(1 + up/down ratio)) / (1 + max drawdown / 10). "
             "Higher is better.",
    'Combined growth %/90d': "Weighted mean of the 30-day (50%) and 90-day (50%) trend slopes, "
                             "expressed as growth per 90 days. Windows without enough quotes are skipped.",
    'Growth 30d %': "Growth of the trend line fitted to the last 30 days, over those 30 days.",
    'Growth 90d %': "Growth of the trend line fitted to the last 90 days, over those 90 days.",
    'Growth 1y %': "Growth of the trend line fitted to the last 365 days, over that year. "
                   "Informational - not part of the score.",
    'Period trend %/90d': "Growth of the screening period's trend line, per 90 days "
                          "(compared with Min trend growth).",
    'Downside dev %': "RMS of the closes below the trend line, in % (compared with Max downside dev).",
    'Max below trend %': "Deepest close below the trend line in the period, in %.",
    'Max drawdown %': "Deepest peak-to-trough fall of the close in the period.",
    'Max daily drop %': "Worst single-day close-to-close fall in the period.",
    'Up/Down ratio': "Upside / downside deviation around the trend line; >1 = more distance above than below.",
    'Sortino': "Annualized Sortino ratio of daily log returns (mean / downside RMS). Informational.",
    'R²': "How well the straight log-trend fits the closes (1 = perfect). Informational only.",
    'Momentum': "🚀 = recent growth exceeds Momentum factor × the trend-implied growth.",
    'Points': "Number of quotes used in the period's regression.",
}


def _window(close_wide, days):
    end = close_wide.index.max()
    win = close_wide.loc[end - pd.Timedelta(days=days):]
    return win.where(win > 0)


def _log_regression(win):
    """NaN-aware OLS of log(close) on the calendar-day index, per column.
    Returns (slope per day, residuals, quote count, R²)."""
    y = np.log(win.to_numpy(dtype=float))
    mask = ~np.isnan(y)
    n = mask.sum(axis=0).astype(float)
    x = ((win.index - win.index[0]).days.to_numpy(dtype=float))[:, None]
    xm = np.where(mask, x, 0.0)
    with np.errstate(invalid='ignore', divide='ignore'):
        x_mean = xm.sum(axis=0) / n
        y_mean = np.nansum(y, axis=0) / n
        dx = np.where(mask, x - x_mean, 0.0)
        dy = np.where(mask, y - y_mean, 0.0)
        slope = (dx * dy).sum(axis=0) / (dx * dx).sum(axis=0)
        resid = np.where(mask, dy - slope * dx, np.nan)
        r2 = 1 - np.nansum(resid ** 2, axis=0) / (dy * dy).sum(axis=0)
    return slope, resid, n, r2


def steady_trend_metrics(close_wide, period_days, momentum_days):
    """Per-ticker metrics over the last period_days (calendar) of close_wide,
    plus the separate SCORE_GROWTH_WINDOWS trends. Returns a DataFrame indexed
    by ticker; no thresholds applied here."""
    if close_wide is None or close_wide.empty:
        return pd.DataFrame()
    end = close_wide.index.max()
    win = _window(close_wide, period_days)
    trading_days = len(win)
    if trading_days < 3:
        return pd.DataFrame()

    # 1. Trend of the screening period.
    slope, resid, n, r2 = _log_regression(win)

    # 2. Downside-only deviation from the trend line; positive residuals
    # (breakouts) only feed the upside deviation, which raises the ratio.
    with np.errstate(invalid='ignore', divide='ignore'):
        downside_dev = np.sqrt(np.nansum(np.minimum(resid, 0) ** 2, axis=0) / n)
        upside_dev = np.sqrt(np.nansum(np.maximum(resid, 0) ** 2, axis=0) / n)
        updown = upside_dev / downside_dev
        max_below = np.nanmin(np.minimum(resid, 0), axis=0)

    # 3./4. Drawdown and daily moves on the ffilled window (a gap counts as one move).
    filled = win.ffill()
    drawdown = (1 - filled / filled.cummax()).max()
    daily = filled.pct_change(fill_method=None)
    max_daily_drop = (-daily.min()).clip(lower=0)

    # 5. Sortino on daily log returns, annualized.
    log_ret = np.log(filled).diff()
    downside_rms = np.sqrt((log_ret.clip(upper=0) ** 2).mean())
    sortino = log_ret.mean() / downside_rms * np.sqrt(TRADING_DAYS_PER_YEAR)

    # 7. Momentum: actual growth over the recent window vs. what the trend implies.
    last = filled.iloc[-1]
    past_rows = filled.loc[:end - pd.Timedelta(days=momentum_days)]
    past = past_rows.iloc[-1] if not past_rows.empty else filled.bfill().iloc[0]
    recent_growth = last / past - 1
    implied_growth = np.expm1(slope * momentum_days)

    out = pd.DataFrame({
        'slope': slope,
        'trend_growth_pct': np.expm1(slope * GROWTH_HORIZON_DAYS) * 100,
        'downside_dev_pct': downside_dev * 100,
        'upside_dev_pct': upside_dev * 100,
        'max_below_trend_pct': np.expm1(max_below) * 100,
        'updown_ratio': updown,
        'r2': r2,
        'points': n.astype(int),
        'coverage_pct': n / trading_days * 100,
    }, index=win.columns)
    out['max_drawdown_pct'] = drawdown * 100
    out['max_daily_drop_pct'] = max_daily_drop * 100
    out['sortino'] = sortino.replace([np.inf, -np.inf], np.nan)
    out['recent_growth_pct'] = recent_growth * 100
    out['implied_growth_pct'] = implied_growth * 100

    # Score inputs: each window's own trend, shown as growth over that window
    # and kept as slope + coverage for combining.
    for days in SCORE_GROWTH_WINDOWS:
        w = _window(close_wide, days)
        w_slope, _, w_n, _ = _log_regression(w)
        out[f'growth_{days}d_pct'] = np.expm1(w_slope * days) * 100
        out[f'slope_{days}d'] = w_slope
        out[f'coverage_{days}d_pct'] = w_n / max(len(w), 1) * 100
    return out


def score_steady_trend(metrics, params):
    """Applies the thresholds in params (keys of STEADY_TREND_PARAMS; None falls
    back to the default) and scores every ticker. Adds 'passes', 'fails' (names
    of the failed criteria), 'momentum' and 'score'; passing tickers first,
    each group best score first."""
    if metrics.empty:
        return metrics
    p = {k: (params.get(k) if params.get(k) is not None else v)
         for k, v in STEADY_TREND_PARAMS.items()}
    m = metrics.copy()
    checks = pd.DataFrame({
        'history': m['coverage_pct'] >= p['min_coverage_pct'],
        'growth': (m['slope'] > 0) & (m['trend_growth_pct'] >= p['min_growth_pct']),
        'downside': m['downside_dev_pct'] <= p['max_downside_dev_pct'],
        'drawdown': m['max_drawdown_pct'] <= p['max_drawdown_pct'],
        'daily drop': m['max_daily_drop_pct'] <= p['max_daily_drop_pct'],
        'up/down': m['updown_ratio'].fillna(np.inf) >= p['min_updown_ratio'],
    })
    m['passes'] = checks.all(axis=1)
    m['fails'] = [', '.join(checks.columns[~row]) for row in checks.to_numpy()]
    m['momentum'] = m['passes'] & (m['implied_growth_pct'] > 0) & (
        m['recent_growth_pct'] > p['momentum_factor'] * m['implied_growth_pct'])

    # Combined growth: weighted mean of the window slopes, expressed as growth
    # per GROWTH_HORIZON_DAYS so the windows are comparable.
    weighted = pd.Series(0.0, index=m.index)
    weights = pd.Series(0.0, index=m.index)
    for days, weight in SCORE_GROWTH_WINDOWS.items():
        ok = (m[f'coverage_{days}d_pct'] >= p['min_coverage_pct']) & m[f'slope_{days}d'].notna()
        weighted += np.where(ok, weight * m[f'slope_{days}d'].fillna(0), 0.0)
        weights += np.where(ok, weight, 0.0)
    m['combined_growth_pct'] = np.expm1(weighted / weights.replace(0, np.nan) * GROWTH_HORIZON_DAYS) * 100

    # 8. Score: rises with combined growth and with the up/down ratio, falls
    # with drawdown.
    ratio = m['updown_ratio'].fillna(SCORE_RATIO_CAP).clip(upper=SCORE_RATIO_CAP)
    m['score'] = (m['combined_growth_pct'] * (1 + np.log1p(ratio))
                  / (1 + m['max_drawdown_pct'] / 10))
    return m.sort_values(['passes', 'score'], ascending=[False, False], na_position='last')


def steady_trend_rows(scored):
    """Records for the dashboard table, rounded for display."""
    rows = []
    for ticker, r in scored.iterrows():
        row = {}
        for col, key in STEADY_TREND_COLUMNS.items():
            if key == 'ticker':
                row[col] = ticker
            elif key == 'passes':
                row[col] = '✓' if r['passes'] else '✗'
            elif key == 'fails':
                row[col] = r['fails']
            elif key == 'momentum':
                row[col] = '🚀' if r['momentum'] else ''
            elif key == 'points':
                row[col] = int(r['points'])
            elif pd.isna(r[key]) or np.isinf(r[key]):
                row[col] = None
            else:
                row[col] = round(float(r[key]), 3 if key == 'r2' else 2)
        rows.append(row)
    return rows
