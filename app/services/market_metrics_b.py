import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

current_datetime = datetime.now()

def metrics_separate_tabs(tickers, us_market_list, procedure_choice, market_mappings):
    # Download data for tickers
    tickers_data = yf.download(tickers, period='6mo')
    # It's good practice to check if tickers_data is empty or if specific columns are missing
    if tickers_data.empty:
        print("No data downloaded. Exiting.")
        return pd.DataFrame() # Return an empty DataFrame

    # Ensure 'Close' column exists for all tickers, otherwise handle
    # For simplicity, this example assumes 'Close' etc. are present if data is downloaded.
    # In a production scenario, you'd add more robust checks here.

    #pd.DataFrame(tickers_data).to_excel('list_tta1.xlsx', sheet_name='sheet1')

    ohlc_data = tickers_data.loc[:, tickers_data.columns.get_level_values(0).isin(['Open', 'High', 'Low', 'Close'])]
    
    # 2. Flatten the multi-level column names (e.g., ('Open', 'AAPL') -> 'Open_AAPL')
    ohlc_data.columns = [f'{price_type}_{ticker}' for price_type, ticker in ohlc_data.columns]
    
    # 3. Reorder columns to group by ticker
    ohlc_data = ohlc_data.reindex(sorted(ohlc_data.columns), axis=1)

    # 4. Save the historical data to a CSV file
    #csv_filename = f"historical_prices_{current_datetime.strftime('%Y%m%d%H%M')}.csv"
    if procedure_choice == "2":
        csv_filename = f"historical_prices_SP500.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")
    elif procedure_choice == "1":
        csv_filename = f"historical_prices_GPW.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")
    elif procedure_choice == "4":
        csv_filename = f"historical_prices_PROD.csv"
        ohlc_data.to_csv(csv_filename)
        print(f"Successfully exported all available daily OHLC data to {csv_filename}")

    # Extract price data
    close_prices = tickers_data['Close']
    open_prices = tickers_data['Open']
    low_prices = tickers_data['Low']
    high_prices = tickers_data['High']

    # Calculate standard metrics
    sma10 = close_prices.rolling(window=10, min_periods=1).mean()
    sma20 = close_prices.rolling(window=20, min_periods=1).mean()
    sma50 = close_prices.rolling(window=50, min_periods=1).mean()
    sma100 = close_prices.rolling(window=100, min_periods=1).mean()
    ema10 = close_prices.ewm(span=10, adjust=False, ignore_na=True).mean()
    ema20 = close_prices.ewm(span=20, adjust=False, ignore_na=True).mean()
    ema50 = close_prices.ewm(span=50, adjust=False, ignore_na=True).mean()
    ema100 = close_prices.ewm(span=100, adjust=False, ignore_na=True).mean()
    ema32_close = close_prices.ewm(span=32, adjust=False, ignore_na=True).mean()
    ema32_open = open_prices.ewm(span=32, adjust=False, ignore_na=True).mean()
    ema32_low = low_prices.ewm(span=32, adjust=False, ignore_na=True).mean()
    ema32_high = high_prices.ewm(span=32, adjust=False, ignore_na=True).mean()
    sma25 = close_prices.rolling(window=25).mean()
    dma25x5 = sma25.shift(5)

    # Check if ema32_close is a Series or DataFrame for the comparison
    # If close_prices is a DataFrame (multiple tickers), ema32_close will also be.
    # The comparison `close_prices > ema32_close` works element-wise.
    close_above_ema32_condition = close_prices > ema32_close
    close_above_sma10_condition = close_prices > sma10
    close_above_sma20_condition = close_prices > sma20
    close_above_sma50_condition = close_prices > sma50
    close_above_sma100_condition = close_prices > sma100
    close_above_ema10_condition = close_prices > ema10
    close_above_ema20_condition = close_prices > ema20
    close_above_ema50_condition = close_prices > ema50
    close_above_ema100_condition = close_prices > ema100
    close_above_dma25x5_condition = close_prices > dma25x5

    # Calculate days_close_above_ema32 for different windows
    days_close_above_ema32_last5 = close_above_ema32_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_ema32_last15 = close_above_ema32_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_ema32_last30 = close_above_ema32_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_sma10_last5 = close_above_sma10_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_sma10_last15 = close_above_sma10_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_sma10_last30 = close_above_sma10_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_sma20_last5 = close_above_sma20_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_sma20_last15 = close_above_sma20_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_sma20_last30 = close_above_sma20_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_sma50_last5 = close_above_sma50_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_sma50_last15 = close_above_sma50_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_sma50_last30 = close_above_sma50_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_sma100_last5 = close_above_sma100_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_sma100_last15 = close_above_sma100_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_sma100_last30 = close_above_sma100_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_ema10_last5 = close_above_ema10_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_ema10_last15 = close_above_ema10_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_ema10_last30 = close_above_ema10_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_ema20_last5 = close_above_ema20_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_ema20_last15 = close_above_ema20_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_ema20_last30 = close_above_ema20_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_ema50_last5 = close_above_ema50_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_ema50_last15 = close_above_ema50_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_ema50_last30 = close_above_ema50_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_ema100_last5 = close_above_ema100_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_ema100_last15 = close_above_ema100_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_ema100_last30 = close_above_ema100_condition.rolling(window=30, min_periods=1).sum()

    days_close_above_dma25x5_last5 = close_above_dma25x5_condition.rolling(window=5, min_periods=1).sum()
    days_close_above_dma25x5_last15 = close_above_dma25x5_condition.rolling(window=15, min_periods=1).sum()
    days_close_above_dma25x5_last30 = close_above_dma25x5_condition.rolling(window=30, min_periods=1).sum()



    ath10 = close_prices.rolling(window=10, min_periods=1).max()
    ath30 = close_prices.rolling(window=30, min_periods=1).max()
    ath30 = ath30.fillna(ath10) # Fill NaN for ath30 if window is too small
    pct_diff_ath10 = ((close_prices - ath10) / ath10) * 100
    pct_diff_ath30 = ((close_prices - ath30) / ath30) * 100


    dfs = {}
    for ticker_symbol_loop in tickers:
        # Ensure the ticker exists in the downloaded data columns
        if ticker_symbol_loop not in close_prices.columns:
            print(f"Ticker {ticker_symbol_loop} not found in downloaded data. Skipping.")
            continue

        df_single_ticker_data = {
            f'Open_{ticker_symbol_loop}': open_prices[ticker_symbol_loop],
            f'Close_{ticker_symbol_loop}': close_prices[ticker_symbol_loop],
            f'Low_{ticker_symbol_loop}': low_prices[ticker_symbol_loop],
            f'High_{ticker_symbol_loop}': high_prices[ticker_symbol_loop],
            f'SMA10_{ticker_symbol_loop}': sma10[ticker_symbol_loop],
            f'SMA20_{ticker_symbol_loop}': sma20[ticker_symbol_loop],
            f'SMA50_{ticker_symbol_loop}': sma50[ticker_symbol_loop],
            f'SMA100_{ticker_symbol_loop}': sma100[ticker_symbol_loop],
            f'EMA10_{ticker_symbol_loop}': ema10[ticker_symbol_loop],
            f'EMA20_{ticker_symbol_loop}': ema20[ticker_symbol_loop],
            f'EMA50_{ticker_symbol_loop}': ema50[ticker_symbol_loop],
            f'EMA100_{ticker_symbol_loop}': ema100[ticker_symbol_loop],
            f'EMA32_Close_{ticker_symbol_loop}': ema32_close[ticker_symbol_loop],
            f'EMA32_Open_{ticker_symbol_loop}': ema32_open[ticker_symbol_loop],
            f'EMA32_Low_{ticker_symbol_loop}': ema32_low[ticker_symbol_loop],
            f'EMA32_High_{ticker_symbol_loop}': ema32_high[ticker_symbol_loop],
            f'DMA25x5_{ticker_symbol_loop}': dma25x5[ticker_symbol_loop],
            # MODIFIED: Add all three days_close_above_ema32 metrics
            f'DaysCloseAboveEMA32_Last5_{ticker_symbol_loop}': days_close_above_ema32_last5[ticker_symbol_loop],
            f'DaysCloseAboveEMA32_Last15_{ticker_symbol_loop}': days_close_above_ema32_last15[ticker_symbol_loop],
            f'DaysCloseAboveEMA32_Last30_{ticker_symbol_loop}': days_close_above_ema32_last15[ticker_symbol_loop],
            f'DaysCloseAboveSMA10_Last5_{ticker_symbol_loop}': days_close_above_sma10_last5[ticker_symbol_loop],
            f'DaysCloseAboveSMA10_Last15_{ticker_symbol_loop}': days_close_above_sma10_last15[ticker_symbol_loop],
            f'DaysCloseAboveSMA10_Last30_{ticker_symbol_loop}': days_close_above_sma10_last30[ticker_symbol_loop],
            f'DaysCloseAboveSMA20_Last5_{ticker_symbol_loop}': days_close_above_sma20_last5[ticker_symbol_loop],
            f'DaysCloseAboveSMA20_Last15_{ticker_symbol_loop}': days_close_above_sma20_last15[ticker_symbol_loop],
            f'DaysCloseAboveSMA20_Last30_{ticker_symbol_loop}': days_close_above_sma20_last30[ticker_symbol_loop],
            f'DaysCloseAboveSMA50_Last5_{ticker_symbol_loop}': days_close_above_sma50_last5[ticker_symbol_loop],
            f'DaysCloseAboveSMA50_Last15_{ticker_symbol_loop}': days_close_above_sma50_last15[ticker_symbol_loop],
            f'DaysCloseAboveSMA50_Last30_{ticker_symbol_loop}': days_close_above_sma50_last30[ticker_symbol_loop],
            f'DaysCloseAboveSMA100_Last5_{ticker_symbol_loop}': days_close_above_sma100_last5[ticker_symbol_loop],
            f'DaysCloseAboveSMA100_Last15_{ticker_symbol_loop}': days_close_above_sma100_last15[ticker_symbol_loop],
            f'DaysCloseAboveSMA100_Last30_{ticker_symbol_loop}': days_close_above_sma100_last30[ticker_symbol_loop],

            f'DaysCloseAboveEMA10_Last5_{ticker_symbol_loop}': days_close_above_ema10_last5[ticker_symbol_loop],
            f'DaysCloseAboveEMA10_Last15_{ticker_symbol_loop}': days_close_above_ema10_last15[ticker_symbol_loop],
            f'DaysCloseAboveEMA10_Last30_{ticker_symbol_loop}': days_close_above_ema10_last30[ticker_symbol_loop],
            f'DaysCloseAboveEMA20_Last5_{ticker_symbol_loop}': days_close_above_ema20_last5[ticker_symbol_loop],
            f'DaysCloseAboveEMA20_Last15_{ticker_symbol_loop}': days_close_above_ema20_last15[ticker_symbol_loop],
            f'DaysCloseAboveEMA20_Last30_{ticker_symbol_loop}': days_close_above_ema20_last30[ticker_symbol_loop],
            f'DaysCloseAboveEMA50_Last5_{ticker_symbol_loop}': days_close_above_ema50_last5[ticker_symbol_loop],
            f'DaysCloseAboveEMA50_Last15_{ticker_symbol_loop}': days_close_above_ema50_last15[ticker_symbol_loop],
            f'DaysCloseAboveEMA50_Last30_{ticker_symbol_loop}': days_close_above_ema50_last30[ticker_symbol_loop],
            f'DaysCloseAboveEMA100_Last5_{ticker_symbol_loop}': days_close_above_ema100_last5[ticker_symbol_loop],
            f'DaysCloseAboveEMA100_Last15_{ticker_symbol_loop}': days_close_above_ema100_last15[ticker_symbol_loop],
            f'DaysCloseAboveEMA100_Last30_{ticker_symbol_loop}': days_close_above_ema100_last30[ticker_symbol_loop],

            f'DaysCloseAboveDMA25x5_Last5_{ticker_symbol_loop}': days_close_above_dma25x5_last5[ticker_symbol_loop],
            f'DaysCloseAboveDMA25x5_Last15_{ticker_symbol_loop}': days_close_above_dma25x5_last15[ticker_symbol_loop],
            f'DaysCloseAboveDMA25x5_Last30_{ticker_symbol_loop}': days_close_above_dma25x5_last30[ticker_symbol_loop],            
            
            f'ath10{ticker_symbol_loop}': ath10[ticker_symbol_loop],
            f'ath30{ticker_symbol_loop}': ath30[ticker_symbol_loop],
            f'pct_diff_ath10{ticker_symbol_loop}': pct_diff_ath10[ticker_symbol_loop],
            f'pct_diff_ath30{ticker_symbol_loop}': pct_diff_ath30[ticker_symbol_loop]
        }
        df_single_ticker = pd.DataFrame(df_single_ticker_data)

        if not df_single_ticker.empty:
            latest_date = df_single_ticker.index.max()
            df_single_ticker = df_single_ticker.loc[[latest_date]]
        dfs[ticker_symbol_loop] = df_single_ticker

    excel_filename = f"listPROD_test_{current_datetime.strftime('%Y%m%d%H%M')}.xlsx"
#               error there with pd.ExcelWriter(excel_filename) as writer
#               ValueError: This sheet is too large! Your sheet size is: 1, 25653 Max sheet size is: 1048576, 16384
#               During handling of the above exception, another exception occurred:
#    with pd.ExcelWriter(excel_filename) as writer:
        # Filter out empty DataFrames from dfs before concatenating
#        valid_dfs = {k: v for k, v in dfs.items() if not v.empty}
#        if valid_dfs:
#            all_data = pd.concat(valid_dfs.values(), axis=1)
            #all_data.to_excel(writer, sheet_name='All_Tickers', index=True)
#        else:
#            print("No valid ticker data to write to 'All_Tickers' sheet.")
#
#        for ticker_symbol_excel, df_excel in dfs.items():
#            if not df_excel.empty:
#                df_excel.to_excel(writer, sheet_name=ticker_symbol_excel, index=True)
#            else:
#                # Optionally, write an empty sheet or a sheet with a message
#                pd.DataFrame({'Message': [f'No data for {ticker_symbol_excel}']}).to_excel(writer, sheet_name=ticker_symbol_excel, index=False)


    market_info_dict = {}
    for ticker_str in tickers:
        try:
            ticker_obj = yf.Ticker(ticker_str)
            market_info_dict[ticker_str] = ticker_obj.info.get('exchange', 'N/A')
        except Exception as e:
            print(f"Could not retrieve market info for {ticker_str}: {e}")
            market_info_dict[ticker_str] = 'ErrorFetchingInfo'

    rows_list = []
    for ticker in tickers:
        market_val = market_info_dict.get(ticker, 'N/A')

        if ticker not in dfs or dfs[ticker].empty:
            row_data = {
                'one': ' ', 'date': '', 'ticker': ticker, 'market': market_val,
                'close': '',
                'DaysCloseAboveEMA32_Last5_': '',
                'DaysCloseAboveEMA32_Last10_': '',
                'DaysCloseAboveEMA32_Last15_': '',
                'DaysCloseAboveSMA10_Last5_': '',
                'DaysCloseAboveSMA10_Last15_': '',
                'DaysCloseAboveSMA10_Last30_': '',
                'DaysCloseAboveSMA20_Last5_': '',
                'DaysCloseAboveSMA20_Last15_': '',
                'DaysCloseAboveSMA20_Last30_': '',
                'DaysCloseAboveSMA50_Last5_': '',
                'DaysCloseAboveSMA50_Last15_': '',
                'DaysCloseAboveSMA50_Last30_': '',
                'DaysCloseAboveSMA100_Last5_': '',
                'DaysCloseAboveSMA100_Last15_': '',
                'DaysCloseAboveSMA100_Last30_': '',
                'DaysCloseAboveEMA10_Last5_': '',
                'DaysCloseAboveEMA10_Last15_': '',
                'DaysCloseAboveEMA10_Last30_': '',
                'DaysCloseAboveEMA20_Last5_': '',
                'DaysCloseAboveEMA20_Last15_': '',
                'DaysCloseAboveEMA20_Last30_': '',
                'DaysCloseAboveEMA50_Last5_': '',
                'DaysCloseAboveEMA50_Last15_': '',
                'DaysCloseAboveEMA50_Last30_': '',
                'DaysCloseAboveEMA100_Last5_': '',
                'DaysCloseAboveEMA100_Last15_': '',
                'DaysCloseAboveEMA100_Last30_': '',
                'DaysCloseAboveDMA25x5_Last5_': '',
                'DaysCloseAboveDMA25x5_Last15_': '',
                'DaysCloseAboveDMA25x5_Last30_': '',
                'pct_diff_ath10': '',
                'pct_diff_ath30': ''
            }
            rows_list.append(row_data)
            continue
        
        df_for_result = dfs[ticker]
        try:
            date_value_str = ''
            if not df_for_result.empty and len(df_for_result.index) > 0:
                timestamp_obj = df_for_result.index[0]
                if pd.notna(timestamp_obj): # Check if timestamp is not NaT
                    if timestamp_obj.tzinfo is None:
                        timestamp_utc = timestamp_obj.tz_localize('UTC')
                    else:
                        timestamp_utc = timestamp_obj.tz_convert('UTC')
                    date_value_str = timestamp_utc.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            
            row_data = {
                'one': ' ',
                'date': date_value_str,
                'ticker': ticker,
                'close': df_for_result.get(f'Close_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                # MODIFIED: Ensure correct column names are fetched
                'DaysCloseAboveEMA32_Last5_': df_for_result.get(f'DaysCloseAboveEMA32_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA32_Last15_': df_for_result.get(f'DaysCloseAboveEMA32_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA32_Last30_': df_for_result.get(f'DaysCloseAboveEMA32_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA10_Last5_': df_for_result.get(f'DaysCloseAboveSMA10_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA10_Last15_': df_for_result.get(f'DaysCloseAboveSMA10_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA10_Last30_': df_for_result.get(f'DaysCloseAboveSMA10_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA20_Last5_': df_for_result.get(f'DaysCloseAboveSMA20_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA20_Last15_': df_for_result.get(f'DaysCloseAboveSMA20_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA20_Last30_': df_for_result.get(f'DaysCloseAboveSMA20_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA50_Last5_': df_for_result.get(f'DaysCloseAboveSMA50_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA50_Last15_': df_for_result.get(f'DaysCloseAboveSMA50_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA50_Last30_': df_for_result.get(f'DaysCloseAboveSMA50_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA100_Last5_': df_for_result.get(f'DaysCloseAboveSMA100_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA100_Last15_': df_for_result.get(f'DaysCloseAboveSMA100_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveSMA100_Last30_': df_for_result.get(f'DaysCloseAboveSMA100_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA10_Last5_': df_for_result.get(f'DaysCloseAboveEMA10_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA10_Last15_': df_for_result.get(f'DaysCloseAboveEMA10_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA10_Last30_': df_for_result.get(f'DaysCloseAboveEMA10_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA20_Last5_': df_for_result.get(f'DaysCloseAboveEMA20_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA20_Last15_': df_for_result.get(f'DaysCloseAboveEMA20_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA20_Last30_': df_for_result.get(f'DaysCloseAboveEMA20_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA50_Last5_': df_for_result.get(f'DaysCloseAboveEMA50_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA50_Last15_': df_for_result.get(f'DaysCloseAboveEMA50_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA50_Last30_': df_for_result.get(f'DaysCloseAboveEMA50_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA100_Last5_': df_for_result.get(f'DaysCloseAboveEMA100_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA100_Last15_': df_for_result.get(f'DaysCloseAboveEMA100_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveEMA100_Last30_': df_for_result.get(f'DaysCloseAboveEMA100_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveDMA25x5_Last5_': df_for_result.get(f'DaysCloseAboveDMA25x5_Last5_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveDMA25x5_Last15_': df_for_result.get(f'DaysCloseAboveDMA25x5_Last15_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'DaysCloseAboveDMA25x5_Last30_': df_for_result.get(f'DaysCloseAboveDMA25x5_Last30_{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'pct_diff_ath10': df_for_result.get(f'pct_diff_ath10{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'pct_diff_ath30': df_for_result.get(f'pct_diff_ath30{ticker}', pd.Series([np.nan], index=df_for_result.index)).iloc[0],
                'market': market_val,
            }
            for k, v_item in row_data.items(): # Renamed v to v_item to avoid conflict with dfs.values()
                if v_item is None or (isinstance(v_item, float) and np.isnan(v_item)):
                    row_data[k] = "" 
            rows_list.append(row_data)
        except Exception as e:
            print(f"Error processing ticker {ticker} for result_df: {e}")
            row_data = {
                'one': ' ', 'date': '', 'ticker': ticker, 'market': market_val,
                'close': '',
                'DaysCloseAboveEMA32_Last5_': '',
                'DaysCloseAboveEMA32_Last15_': '',
                'DaysCloseAboveEMA32_Last30_': '',
                'DaysCloseAboveSMA10_Last5_': '',
                'DaysCloseAboveSMA10_Last15_': '',
                'DaysCloseAboveSMA10_Last30_': '',
                'DaysCloseAboveSMA20_Last5_': '',
                'DaysCloseAboveSMA20_Last15_': '',
                'DaysCloseAboveSMA20_Last30_': '',
                'DaysCloseAboveSMA50_Last5_': '',
                'DaysCloseAboveSMA50_Last15_': '',
                'DaysCloseAboveSMA50_Last30_': '',
                'DaysCloseAboveSMA100_Last5_': '',
                'DaysCloseAboveSMA100_Last15_': '',
                'DaysCloseAboveSMA100_Last30_': '',
                'DaysCloseAboveEMA10_Last5_': '',
                'DaysCloseAboveEMA10_Last15_': '',
                'DaysCloseAboveEMA10_Last30_': '',
                'DaysCloseAboveEMA20_Last5_': '',
                'DaysCloseAboveEMA20_Last15_': '',
                'DaysCloseAboveEMA20_Last30_': '',
                'DaysCloseAboveEMA50_Last5_': '',
                'DaysCloseAboveEMA50_Last15_': '',
                'DaysCloseAboveEMA50_Last30_': '',
                'DaysCloseAboveEMA100_Last5_': '',
                'DaysCloseAboveEMA100_Last15_': '',
                'DaysCloseAboveEMA100_Last30_': '',
                'DaysCloseAboveDMA25x5_Last5_': '',
                'DaysCloseAboveDMA25x5_Last15_': '',
                'DaysCloseAboveDMA25x5_Last30_': '',

                'pct_diff_ath10': '',
                'pct_diff_ath30': ''
            }
            rows_list.append(row_data)

    result_df = pd.DataFrame(rows_list)
    if result_df.empty:
        print("Result DataFrame is empty. Cannot proceed with market mapping or URL generation.")
        #result_df.to_excel('list_tta.xlsx', sheet_name='sheet1', index=False) # Save empty or error state
        return result_df

    result_df['market_real'] = result_df['market'].map(market_mappings).fillna('N/A')
    
    def generate_tradingview_url(row):
        market_real_val = row['market_real']
        ticker_val = row['ticker']
        if isinstance(market_real_val, str) and market_real_val != 'N/A' and ticker_val:
            ticker_for_url = str(ticker_val).split('.')[0] 
            return f"https://www.tradingview.com/chart/?symbol={market_real_val}:{ticker_for_url}"
        else:
            return 'N/A'
    result_df['tradingview_url'] = result_df.apply(generate_tradingview_url, axis=1)
    
    if not result_df.empty:
        cols = list(result_df.columns)
        # Define the exact desired order, including the new columns
        # Adjust this list to match your preferred column order
        desired_order = [
            'ticker', 'close',
            'pct_diff_ath10', 'pct_diff_ath30',

            'DaysCloseAboveSMA10_Last5_',   
            'DaysCloseAboveEMA10_Last5_',  
            'DaysCloseAboveSMA20_Last5_',
            'DaysCloseAboveEMA20_Last5_',
            'DaysCloseAboveEMA32_Last5_',
            'DaysCloseAboveSMA50_Last5_',  
            'DaysCloseAboveEMA50_Last5_',   
            'DaysCloseAboveSMA100_Last5_',    
            'DaysCloseAboveEMA100_Last5_',       
            'DaysCloseAboveDMA25x5_Last5_',  
            'DaysCloseAboveSMA10_Last15_',    
            'DaysCloseAboveSMA20_Last15_',
            'DaysCloseAboveSMA50_Last15_', 
            'DaysCloseAboveSMA100_Last15_',  
            'DaysCloseAboveEMA10_Last15_',     
            'DaysCloseAboveEMA20_Last15_',
            'DaysCloseAboveEMA32_Last15_',
            'DaysCloseAboveEMA50_Last15_',   
            'DaysCloseAboveEMA100_Last15_',   
            'DaysCloseAboveDMA25x5_Last15_',         
            'DaysCloseAboveSMA10_Last30_',   
            'DaysCloseAboveSMA20_Last30_',      
            'DaysCloseAboveSMA50_Last30_',   
            'DaysCloseAboveSMA100_Last30_',            
            'DaysCloseAboveEMA10_Last30_',   
            'DaysCloseAboveEMA20_Last30_',      
            'DaysCloseAboveEMA32_Last30_',           
            'DaysCloseAboveEMA50_Last30_',   
            'DaysCloseAboveEMA100_Last30_',       
            'DaysCloseAboveDMA25x5_Last30_', 
            'market', 'market_real', 'tradingview_url'
            ,'date'
        ]
        
        # Filter out any columns in desired_order that might not exist in result_df
        # (e.g., if all tickers failed processing)
        ordered_cols = [col for col in desired_order if col in result_df.columns]
        
        # Add any remaining columns from result_df not in desired_order to the end
        remaining_cols = [col for col in result_df.columns if col not in ordered_cols]
        final_cols_order = ordered_cols + remaining_cols
        
        result_df = result_df[final_cols_order]
            
    #result_df.to_excel('list_tta.xlsx', sheet_name='sheet1', index=False)
    return result_df