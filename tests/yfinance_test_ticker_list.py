import pandas as pd
from yahoo_fin import stock_info as si

def get_stock_info(exchange):
    """
    Retrieves ticker, dividend information, sector, and industry for stocks in a given exchange using yahoo_fin.

    Args:
        exchange (str): The stock exchange ('NYSE' or 'NASDAQ').

    Returns:
        pandas.DataFrame: A DataFrame containing the stock information, or None if an error occurs.
    """
    try:
        if exchange.upper() == 'NYSE':
            tickers = si.tickers_nyse()
        elif exchange.upper() == 'NASDAQ':
            tickers = si.tickers_nasdaq()
        else:
            print("Invalid exchange. Please specify 'NYSE' or 'NASDAQ'.")
            return None

        data = []
        for ticker in tickers:
            try:
                quote_table = si.get_quote_table(ticker)

                # Extract relevant information
                dividend_rate = quote_table.get('Forward Annual Dividend Rate', None)
                sector = quote_table.get('Sector', None)
                industry = quote_table.get('Industry', None)

                data.append({
                    'Ticker': ticker,
                    'Dividend Rate': dividend_rate,
                    'Sector': sector,
                    'Industry': industry,
                })

            except Exception as e:
                print(f"Error processing {ticker}: {e}")

        return pd.DataFrame(data)

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Get information for NYSE stocks
nyse_info = get_stock_info('NYSE')

# Get information for NASDAQ stocks
nasdaq_info = get_stock_info('NASDAQ')

# Combine and display the results
if nyse_info is not None and nasdaq_info is not None:
    all_info = pd.concat([nyse_info, nasdaq_info], ignore_index=True)
    print(all_info)

    # Optionally save the result to a CSV file
    all_info.to_csv("stock_info_yahoo_fin.csv", index=False)