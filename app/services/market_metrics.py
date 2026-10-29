import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

EXCHANGE_CACHE_FILE = "ticker_exchange_cache.json"


def _load_exchange_cache():
    if os.path.exists(EXCHANGE_CACHE_FILE):
        try:
            with open(EXCHANGE_CACHE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_exchange_cache(cache):
    with open(EXCHANGE_CACHE_FILE, "w") as f:
        json.dump(cache, f)


def _fetch_exchange(ticker_str):
    try:
        return ticker_str, yf.Ticker(ticker_str).info.get('exchange', 'N/A')
    except Exception:
        return ticker_str, 'ErrorFetchingInfo'


def get_market_info(tickers, max_workers=20):
    """Resolve each ticker's listing exchange, using a disk cache and threaded fetch for misses."""
    cache = _load_exchange_cache()
    market_info_dict = {t: cache[t] for t in tickers if t in cache}
    missing = [t for t in tickers if t not in cache]

    if missing:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_fetch_exchange, t) for t in missing]
            for future in as_completed(futures):
                ticker_str, exchange = future.result()
                market_info_dict[ticker_str] = exchange
                if exchange not in ('N/A', 'ErrorFetchingInfo'):
                    cache[ticker_str] = exchange
        _save_exchange_cache(cache)

    return market_info_dict


def seed_exchange_cache(exchange_by_ticker):
    """Add known exchange codes to the cache (existing entries win), so large
    universes whose exchange is already known skip the slow per-ticker .info call."""
    cache = _load_exchange_cache()
    added = {t: ex for t, ex in exchange_by_ticker.items() if t not in cache}
    if added:
        cache.update(added)
        _save_exchange_cache(cache)
    return len(added)


# Dollar-volume liquidity filter (Close * Volume, unadjusted Close).
DOLLAR_VOLUME_DAYS = 50        # look-back window in sessions
DOLLAR_VOLUME_MIN_DAYS = 40    # fewer valid sessions (recent IPO, gaps) -> excluded


def median_dollar_volume(tickers_data, tickers, days=DOLLAR_VOLUME_DAYS, min_days=DOLLAR_VOLUME_MIN_DAYS):
    """Median daily dollar volume over the last `days` sessions per ticker (NaN if
    fewer than `min_days` valid sessions). Median, so one earnings or index-rebalance
    spike can't lift a thin name over the threshold."""
    out = {}
    for ticker in tickers:
        if (ticker, 'Close') not in tickers_data.columns or (ticker, 'Volume') not in tickers_data.columns:
            out[ticker] = np.nan
            continue
        dv = (tickers_data[(ticker, 'Close')] * tickers_data[(ticker, 'Volume')]).dropna().tail(days)
        out[ticker] = dv.median() if len(dv) >= min_days else np.nan
    return pd.Series(out, dtype=float)

# How much daily history the chart CSVs (historical_prices_*.csv) hold. The
# DiNapoli engine needs years, not months: MA200, weekly/monthly swings and
# weekly/monthly Fibo levels are meaningless on ~125 bars (the old 181 days).
# The tail-based metrics below (DaysCloseAbove..._LastN, ATH10/30, pct change)
# are unaffected by the longer window.
HISTORY_DAYS = 3 * 365

OHLCV = ['Open', 'High', 'Low', 'Close', 'Volume']

# Yahoo intermittently returns nothing for single tickers ("possibly
# delisted") inside a large batch, even though the same ticker downloads fine
# seconds later. Such tickers are re-requested this many times, after a
# short pause, before being given up on.
DOWNLOAD_RETRIES = 2
DOWNLOAD_RETRY_PAUSE_S = 3.0


def _empty_tickers(data, tickers):
    """Tickers with no usable Close in a yf.download(group_by='ticker') result."""
    if data is None or data.empty:
        return list(tickers)
    if not isinstance(data.columns, pd.MultiIndex):
        # Single-ticker download comes back with flat columns.
        close = data.get('Close')
        return list(tickers) if close is None or close.dropna().empty else []
    present = set(data.columns.get_level_values(0))
    return [t for t in tickers
            if t not in present or (t, 'Close') not in data.columns
            or data[(t, 'Close')].dropna().empty]


def _yf_download(tickers, start_date, end_date):
    """yf.download() with a retry of just the tickers that came back empty.

    Always re-downloads the full window (no delta/merge): Yahoo's OHLC is
    split-adjusted retroactively, so appending new rows to an old CSV would
    put pre- and post-split prices on different scales, and a short window
    saves little anyway - the cost is per ticker request, not per day
    (measured: 200 tickers, 3y 15.5s vs 10d 11.6s).
    """
    kwargs = dict(start=start_date, end=end_date, auto_adjust=False, group_by='ticker')
    data = yf.download(tickers, **kwargs)

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        missing = _empty_tickers(data, tickers)
        if not missing:
            break
        print(f"yfinance: {len(missing)} ticker(s) empty, retry {attempt}/{DOWNLOAD_RETRIES}: "
              f"{', '.join(missing[:15])}{' ...' if len(missing) > 15 else ''}")
        time.sleep(DOWNLOAD_RETRY_PAUSE_S)
        try:
            again = yf.download(missing, **kwargs)
        except Exception as e:
            print(f"yfinance: retry {attempt} failed: {e}")
            continue
        if again is None or again.empty:
            continue
        if data is None or data.empty or not isinstance(data.columns, pd.MultiIndex):
            data = again   # nothing (usable) from the first pass, or single ticker
            continue
        if not isinstance(again.columns, pd.MultiIndex):
            again.columns = pd.MultiIndex.from_product([[missing[0]], again.columns])
        data = pd.concat([data.drop(columns=missing, level=0, errors='ignore'), again], axis=1)

    still = _empty_tickers(data, tickers)
    if still and len(still) < len(tickers):
        print(f"yfinance: no data after {DOWNLOAD_RETRIES} retries for: {', '.join(still)}")
    return data


def _flatten_ohlcv(tickers_data, tickers):
    """yf.download() output -> wide frame with Open_T / High_T / Low_T / Close_T /
    Volume_T columns (alphabetical), indexed by 'Date'."""
    if isinstance(tickers_data.columns, pd.MultiIndex):
        ohlc_data = tickers_data.loc[:, tickers_data.columns.get_level_values(1).isin(OHLCV)]
        ohlc_data.columns = [f'{price_type}_{ticker}' for ticker, price_type in ohlc_data.columns]
    else:
        single_ticker = tickers[0]
        cols = [c for c in OHLCV if c in tickers_data.columns]
        ohlc_data = tickers_data[cols].copy()
        ohlc_data.columns = [f'{col}_{single_ticker}' for col in ohlc_data.columns]
    ohlc_data = ohlc_data.reindex(sorted(ohlc_data.columns), axis=1)
    ohlc_data.index.name = 'Date'
    return ohlc_data


def download_ohlc_to_csv(tickers, csv_filename, days=HISTORY_DAYS):
    """Download daily OHLCV for `tickers` and write it to `csv_filename` (wide format).

    Lightweight refresh used by the positions chart: same download + flatten logic
    as metrics_separate_tabs (Open_TICKER / High_TICKER / Low_TICKER / Close_TICKER /
    Volume_TICKER, indexed by Date), but without the technical-metric computation.
    Returns True on success, False if nothing was downloaded.
    """
    if not tickers:
        print("download_ohlc_to_csv: no tickers given, skipping.")
        return False

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    try:
        tickers_data = _yf_download(tickers, start_date, end_date)
    except Exception as e:
        print(f"download_ohlc_to_csv: yfinance error: {e}")
        return False

    if tickers_data is None or tickers_data.empty:
        print("download_ohlc_to_csv: no data returned.")
        return False

    ohlc_data = _flatten_ohlcv(tickers_data, tickers)
    ohlc_data.to_csv(csv_filename)
    print(f"download_ohlc_to_csv: wrote {csv_filename} ({len(ohlc_data)} rows, {len(tickers)} tickers).")
    return True


def metrics_separate_tabs(tickers, procedure_choice, market_mappings, min_dollar_volume=None):
    """
    Pobiera dane giełdowe, oblicza wskaźniki techniczne i zwraca oczyszczony DataFrame,
    gotowy do dalszego przetwarzania i serializacji JSON.

    min_dollar_volume: if given, tickers whose median 50-day dollar volume is below it
    are dropped (from the CSV and the metrics) and an 'avg_dollar_vol_50_m' column
    (USD millions) is added.
    """
    print(f"Rozpoczynam pobieranie danych dla {len(tickers)} tickerów...")

    # Krok 1: Pobieranie danych historycznych
    end_date = datetime.now()
    # Długa historia - potrzebna wykresom (MA200, trend W/M, poziomy DiNapoli);
    # metryki poniżej liczą z ogona serii, więc długość okna ich nie zmienia.
    start_date = end_date - timedelta(days=HISTORY_DAYS)

    try:
        tickers_data = _yf_download(tickers, start_date, end_date)
    except Exception as e:
        print(f"Wystąpił błąd podczas pobierania danych z yfinance: {e}")
        return pd.DataFrame()

    if tickers_data.empty:
        print("Nie udało się pobrać żadnych danych. Zatrzymywanie skryptu.")
        return pd.DataFrame()

    # --- START: Added code to save historical data for graphing ---
    # This section processes and saves the downloaded OHLC data to a CSV file,
    # which is required by the graph.py script.

    # 1-4. Select OHLCV, flatten ('TICKER', 'Metric') -> 'Metric_TICKER'
    # (e.g. 'Close_AAPL'), sort columns and name the index 'Date'.
    if not tickers:
        return pd.DataFrame()

    dollar_vol = None
    if min_dollar_volume is not None and isinstance(tickers_data.columns, pd.MultiIndex):
        dollar_vol = median_dollar_volume(tickers_data, tickers)
        keep = dollar_vol[dollar_vol >= min_dollar_volume].index.tolist()
        dropped = len(tickers) - len(keep)
        print(f"Dollar-volume filter: dropped {dropped} of {len(tickers)} tickers below "
              f"${min_dollar_volume / 1e6:.0f}M/day (median of {DOLLAR_VOLUME_DAYS} sessions), {len(keep)} kept.")
        if not keep:
            return pd.DataFrame()
        tickers = keep
        tickers_data = tickers_data.loc[:, tickers_data.columns.get_level_values(0).isin(keep)]

    ohlc_data = _flatten_ohlcv(tickers_data, tickers)

    # 5. Save data to the appropriate CSV file based on procedure_choice.
    # The choice determines the output filename for different market data sets (SP500, GPW, etc.)[2].
    if procedure_choice in ["2", "6"]:
        csv_filename = "historical_prices_SP500.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")
    elif procedure_choice in ["1", "5"]:
        csv_filename = "historical_prices_GPW.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")
    elif procedure_choice in ["4", "7"]:
        csv_filename = "historical_prices_PROD.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")
    elif procedure_choice in ["3", "10"]:
        csv_filename = "historical_prices_US.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")
    elif procedure_choice in ["12"]:
        csv_filename = "historical_prices_ETF.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")

    # --- END: Added code ---

    print("Pobieranie danych zakończone. Przetwarzanie wskaźników...")

    data_flat = {}
    for ticker in tickers:
        if isinstance(tickers_data.columns, pd.MultiIndex):
            if ticker in tickers_data and not tickers_data[ticker].empty:
                df_ticker = tickers_data[ticker].dropna(subset=['Close'])
                for col in df_ticker.columns:
                    data_flat[f"{ticker}_{col}"] = df_ticker[col]
        else: # Handle single ticker case
            df_ticker = tickers_data.dropna(subset=['Close'])
            for col in df_ticker.columns:
                 data_flat[f"{tickers[0]}_{col}"] = df_ticker[col]


    df = pd.DataFrame(data_flat)

    # Krok 2: Obliczanie wskaźników technicznych
    results = {}
    for ticker in tickers:
        close_col = f'{ticker}_Close'
        if close_col not in df.columns:
            continue

        close_prices = df[close_col].dropna()
        if len(close_prices) < 2: # Pomiń, jeśli mamy mniej niż 2 punkty danych
            continue

        last_valid_idx = close_prices.last_valid_index()

        # Obliczenia wskaźników
        sma10 = close_prices.rolling(window=10).mean()
        sma20 = close_prices.rolling(window=20).mean()
        sma50 = close_prices.rolling(window=50).mean()
        sma100 = close_prices.rolling(window=100).mean()
        ema10 = close_prices.ewm(span=10, adjust=False).mean()
        ema20 = close_prices.ewm(span=20, adjust=False).mean()
        ema32 = close_prices.ewm(span=32, adjust=False).mean()
        ema50 = close_prices.ewm(span=50, adjust=False).mean()
        ema100 = close_prices.ewm(span=100, adjust=False).mean()
        ath10 = close_prices.rolling(window=10).max()
        ath30 = close_prices.rolling(window=30).max()
        sma25 = close_prices.rolling(window=25).mean()
        dma25x5 = sma25.shift(5)

        last_close = close_prices.loc[last_valid_idx]
        last_ath10 = ath10.loc[last_valid_idx]
        last_ath30 = ath30.loc[last_valid_idx]

        # --- POCZĄTEK MODYFIKACJI 1: Obliczenie procentowej zmiany ---
        daily_change = close_prices.pct_change().iloc[-1]
        pct_change_last = daily_change * 100
        # --- KONIEC MODYFIKACJI 1 ---

        results[ticker] = {
            'ticker': ticker,
            'date': last_valid_idx.isoformat(),
            'close': last_close,
            'pct_diff_ath10': ((last_close - last_ath10) / last_ath10) * 100 if pd.notna(last_ath10) and last_ath10 != 0 else None,
            'pct_diff_ath30': ((last_close - last_ath30) / last_ath30) * 100 if pd.notna(last_ath30) and last_ath30 != 0 else None,
            'DaysCloseAboveSMA10_Last5_': (close_prices.tail(5) > sma10.tail(5)).sum(),
            'DaysCloseAboveEMA10_Last5_': (close_prices.tail(5) > ema10.tail(5)).sum(),
            'DaysCloseAboveSMA20_Last5_': (close_prices.tail(5) > sma20.tail(5)).sum(),
            'DaysCloseAboveEMA20_Last5_': (close_prices.tail(5) > ema20.tail(5)).sum(),
            'DaysCloseAboveEMA32_Last5_': (close_prices.tail(5) > ema32.tail(5)).sum(),
            'DaysCloseAboveSMA50_Last5_': (close_prices.tail(5) > sma50.tail(5)).sum(),
            'DaysCloseAboveEMA50_Last5_': (close_prices.tail(5) > ema50.tail(5)).sum(),
            'DaysCloseAboveSMA100_Last5_': (close_prices.tail(5) > sma100.tail(5)).sum(),
            'DaysCloseAboveEMA100_Last5_': (close_prices.tail(5) > ema100.tail(5)).sum(),
            'DaysCloseAboveDMA25x5_Last5_': (close_prices.tail(5) > dma25x5.tail(5)).sum(),
            'DaysCloseAboveSMA10_Last15_': (close_prices.tail(15) > sma10.tail(15)).sum(),
            'DaysCloseAboveEMA10_Last15_': (close_prices.tail(15) > ema10.tail(15)).sum(),
            'DaysCloseAboveSMA20_Last15_': (close_prices.tail(15) > sma20.tail(15)).sum(),
            'DaysCloseAboveEMA20_Last15_': (close_prices.tail(15) > ema20.tail(15)).sum(),
            'DaysCloseAboveEMA32_Last15_': (close_prices.tail(15) > ema32.tail(15)).sum(),
            'DaysCloseAboveSMA50_Last15_': (close_prices.tail(15) > sma50.tail(15)).sum(),
            'DaysCloseAboveEMA50_Last15_': (close_prices.tail(15) > ema50.tail(15)).sum(),
            'DaysCloseAboveSMA100_Last15_': (close_prices.tail(15) > sma100.tail(15)).sum(),
            'DaysCloseAboveEMA100_Last15_': (close_prices.tail(15) > ema100.tail(15)).sum(),
            'DaysCloseAboveDMA25x5_Last15_': (close_prices.tail(15) > dma25x5.tail(15)).sum(),
            'DaysCloseAboveSMA10_Last30_': (close_prices.tail(30) > sma10.tail(30)).sum(),
            'DaysCloseAboveEMA10_Last30_': (close_prices.tail(30) > ema10.tail(30)).sum(),
            'DaysCloseAboveSMA20_Last30_': (close_prices.tail(30) > sma20.tail(30)).sum(),
            'DaysCloseAboveEMA20_Last30_': (close_prices.tail(30) > ema20.tail(30)).sum(),
            'DaysCloseAboveEMA32_Last30_': (close_prices.tail(30) > ema32.tail(30)).sum(),
            'DaysCloseAboveSMA50_Last30_': (close_prices.tail(30) > sma50.tail(30)).sum(),
            'DaysCloseAboveEMA50_Last30_': (close_prices.tail(30) > ema50.tail(30)).sum(),
            'DaysCloseAboveSMA100_Last30_': (close_prices.tail(30) > sma100.tail(30)).sum(),
            'DaysCloseAboveEMA100_Last30_': (close_prices.tail(30) > ema100.tail(30)).sum(),
            'DaysCloseAboveDMA25x5_Last30_': (close_prices.tail(30) > dma25x5.tail(30)).sum(),
            'pct_change_last': pct_change_last, # Dodanie nowej metryki do słownika
        }
        if dollar_vol is not None:
            results[ticker]['avg_dollar_vol_50_m'] = round(dollar_vol[ticker] / 1e6, 2)

    if not results:
        print("Nie udało się przetworzyć żadnych tickerów.")
        return pd.DataFrame()

    result_df = pd.DataFrame.from_dict(results, orient='index')

    print("Pobieranie informacji o rynkach...")
    # Krok 3: Dodawanie informacji o giełdzie i URL
    market_info_dict = get_market_info(result_df['ticker'].tolist())

    result_df['market'] = result_df['ticker'].map(market_info_dict)
    result_df['market_real'] = result_df['market'].map(market_mappings).fillna('N/A')

    def generate_tradingview_url(row):
        market_real_val = row['market_real']
        ticker_val = row['ticker']
        if market_real_val != 'N/A' and isinstance(ticker_val, str):
            ticker_for_url = ticker_val.split('.')[0]
            return f"https://www.tradingview.com/chart/?symbol={market_real_val}:{ticker_for_url}"
        return 'N/A'

    result_df['tradingview_url'] = result_df.apply(generate_tradingview_url, axis=1)

    # Krok 4: Oczyszczanie i konwersja typów danych
    print("Końcowa konwersja typów danych dla pełnej kompatybilności...")
    json_records = result_df.to_json(orient='records', date_format='iso')
    list_of_dicts = json.loads(json_records)
    final_df = pd.DataFrame(list_of_dicts)

    # Krok 5: Ustawienie ostatecznej kolejności kolumn
    # --- POCZĄTEK MODYFIKACJI 2: Dodanie nowej kolumny do listy ---
    desired_order = [
        'ticker', 'close', 'pct_diff_ath10', 'pct_diff_ath30',
        'DaysCloseAboveSMA10_Last5_', 'DaysCloseAboveEMA10_Last5_',
        'DaysCloseAboveSMA20_Last5_', 'DaysCloseAboveEMA20_Last5_',
        'DaysCloseAboveEMA32_Last5_', 'DaysCloseAboveSMA50_Last5_',
        'DaysCloseAboveEMA50_Last5_', 'DaysCloseAboveSMA100_Last5_',
        'DaysCloseAboveEMA100_Last5_', 'DaysCloseAboveDMA25x5_Last5_',
        'DaysCloseAboveSMA10_Last15_', 'DaysCloseAboveEMA10_Last15_',
        'DaysCloseAboveSMA20_Last15_', 'DaysCloseAboveEMA20_Last15_',
        'DaysCloseAboveEMA32_Last15_', 'DaysCloseAboveSMA50_Last15_',
        'DaysCloseAboveEMA50_Last15_', 'DaysCloseAboveSMA100_Last15_',
        'DaysCloseAboveEMA100_Last15_', 'DaysCloseAboveDMA25x5_Last15_',
        'DaysCloseAboveSMA10_Last30_', 'DaysCloseAboveEMA10_Last30_',
        'DaysCloseAboveSMA20_Last30_', 'DaysCloseAboveEMA20_Last30_',
        'DaysCloseAboveEMA32_Last30_', 'DaysCloseAboveSMA50_Last30_',
        'DaysCloseAboveEMA50_Last30_', 'DaysCloseAboveSMA100_Last30_',
        'DaysCloseAboveEMA100_Last30_', 'DaysCloseAboveDMA25x5_Last30_',
        'market', 'market_real', 'tradingview_url', 'date',
        'pct_change_last', # <-- Nowa metryka na samym końcu
        'avg_dollar_vol_50_m',
    ]
    # --- KONIEC MODYFIKACJI 2 ---

    # Zabezpieczenie na wypadek, gdyby któraś kolumna nie została wygenerowana
    ordered_cols = [col for col in desired_order if col in final_df.columns]
    # Zastosowanie nowej kolejności
    final_df = final_df[ordered_cols]

    final_df.to_csv('final_df_metrics.csv', index=False)
    print("Przetwarzanie zakończone. Zwracam oczyszczony i uporządkowany DataFrame.")
    print(final_df)
    return final_df
