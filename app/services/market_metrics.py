import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

def metrics_separate_tabs(tickers, procedure_choice, market_mappings):
    """
    Pobiera dane giełdowe, oblicza wskaźniki techniczne i zwraca oczyszczony DataFrame,
    gotowy do dalszego przetwarzania i serializacji JSON.
    """
    print(f"Rozpoczynam pobieranie danych dla {len(tickers)} tickerów...")

    # Krok 1: Pobieranie danych historycznych
    end_date = datetime.now()
    # Pobieramy dane z jednego dnia więcej, aby mieć pewność, że mamy dane do obliczenia pct_change()
    start_date = end_date - timedelta(days=181)

    try:
        tickers_data = yf.download(
            tickers,
            start=start_date,
            end=end_date,
            auto_adjust=False,
            group_by='ticker'
        )
    except Exception as e:
        print(f"Wystąpił błąd podczas pobierania danych z yfinance: {e}")
        return pd.DataFrame()

    if tickers_data.empty:
        print("Nie udało się pobrać żadnych danych. Zatrzymywanie skryptu.")
        return pd.DataFrame()

    # --- START: Added code to save historical data for graphing ---
    # This section processes and saves the downloaded OHLC data to a CSV file,
    # which is required by the graph.py script.

    # 1. Select OHLC columns. Handle both MultiIndex (multiple tickers) and single Index (one ticker).
    if isinstance(tickers_data.columns, pd.MultiIndex):
        ohlc_data = tickers_data.loc[:, tickers_data.columns.get_level_values(1).isin(['Open', 'High', 'Low', 'Close'])]
        # 2. Flatten column names from ('TICKER', 'Metric') to 'Metric_TICKER' (e.g., 'Close_AAPL').
        ohlc_data.columns = [f'{price_type}_{ticker}' for ticker, price_type in ohlc_data.columns]
    else:
        # Handle the case for a single ticker download.
        if not tickers:
             return pd.DataFrame() # Return empty if no tickers
        single_ticker = tickers[0]
        ohlc_data = tickers_data[['Open', 'High', 'Low', 'Close']].copy()
        ohlc_data.columns = [f'{col}_{single_ticker}' for col in ohlc_data.columns]

    # 3. Reorder columns alphabetically for consistency.
    ohlc_data = ohlc_data.reindex(sorted(ohlc_data.columns), axis=1)

    # 4. Name the index 'Date' as expected by the graphing script.
    ohlc_data.index.name = 'Date'

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

    if not results:
        print("Nie udało się przetworzyć żadnych tickerów.")
        return pd.DataFrame()

    result_df = pd.DataFrame.from_dict(results, orient='index')

    print("Pobieranie informacji o rynkach...")
    # Krok 3: Dodawanie informacji o giełdzie i URL
    market_info_dict = {}
    for ticker_str in result_df['ticker']:
        try:
            ticker_obj = yf.Ticker(ticker_str)
            market_info_dict[ticker_str] = ticker_obj.info.get('exchange', 'N/A')
        except Exception:
            market_info_dict[ticker_str] = 'ErrorFetchingInfo'

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
        'pct_change_last' # <-- Nowa metryka na samym końcu
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
