import yfinance as yf
from datetime import datetime, timedelta
import statistics
import pandas as pd
from yahoo_fin import stock_info



def get_sp500_tickers():
    # Source: Example CSV file or online resource for S&P 500 tickers
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    sp500_df = pd.read_csv(url)
    return sp500_df['Symbol'].tolist()

def get_nasdaq_tickers():
    """Pobiera listę tickerów z NASDAQ 100."""
    try:
        nasdaq_tickers = stock_info.tickers_nasdaq()
        return nasdaq_tickers
    except Exception as e:
        print(f"Błąd podczas pobierania tickerów NASDAQ 100: {e}")
        return []


def fetch_dividend_data_last_year(ticker_symbol):
    """
    Fetch dividend data for the last year using yfinance.

    Parameters:
        ticker_symbol (str): Stock ticker symbol (e.g., "MSFT").

    Returns:
        tuple: A tuple containing:
            - pandas.Series: Series of dividend payments within the last year.
            - float: Median dividend value.
    """
    try:
        # Create a Ticker object
        ticker = yf.Ticker(ticker_symbol)

        # Fetch historical dividends
        dividends = ticker.dividends

        # Get today's date and calculate the date one year ago
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)

        # Filter dividends for the last year
        filtered_dividends = dividends.loc[one_year_ago.strftime('%Y-%m-%d'):today.strftime('%Y-%m-%d')]

        # Calculate median dividend
        if len(filtered_dividends) == 0:
            median_dividend = 0  # Handle cases with no dividends
        else:
            median_dividend = statistics.median(filtered_dividends)

        return filtered_dividends, median_dividend

    except Exception as e:
        raise RuntimeError(f"Failed to fetch dividend data for {ticker_symbol}: {e}")

def get_capitalization_volume(ticker_symbol):
    try:
    # Convert ticker_symbol to a yfinance.Ticker object
        ticker = yf.Ticker(ticker_symbol)
    
    # Extract market cap and average volume
        market_cap = ticker.info.get("marketCap")
        avg_volume = ticker.info.get("averageVolume")
        sector  = ticker.info.get("sector") 
        industry  = ticker.info.get("industry") 

        return  market_cap, avg_volume, sector, industry

    except Exception as e:
        print(f"Error fetching capitalization_volume data  for {ticker}: {e}")

def get_current_price(ticker_symbol):
    # Convert ticker_symbol to a yfinance.Ticker object
    ticker = yf.Ticker(ticker_symbol)
    
    # Access the info dictionary and retrieve the current price
    current_price = ticker.info.get('currentPrice')
    
    if current_price is None:
        raise ValueError(f"Current price not available for {ticker_symbol}")
    
    return current_price

def get_dividend_frequency(ticker_symbol):
    # Create a Ticker object
    ticker = yf.Ticker(ticker_symbol)
    
    # Get the dividend history as a pandas Series
    dividends = ticker.dividends
    
    if dividends.empty:
        dividend_period_multiplier = 1
        return f"No dividend history available for {ticker_symbol}.", dividend_period_multiplier 
    
    # Get the time differences between consecutive dividend dates
    time_deltas = dividends.index.to_series().diff().dropna()
    
    # Convert time deltas to days and find the most common interval
    average_days = time_deltas.dt.days.mean()
    
    # Determine frequency based on average days
    if average_days <= 95:  # ~3 months
        frequency = "Quarterly"
        dividend_period_multiplier = 4
    elif average_days <= 190:  # ~6 months
        frequency = "Semi-Annually"
        dividend_period_multiplier = 2
    elif average_days <= 370:  # ~1 year
        frequency = "Annually"
        dividend_period_multiplier = 1
    else:
        frequency = "Irregular"
        dividend_period_multiplier = 1
    
    return f"{ticker_symbol} pays dividends {frequency} (average interval: {average_days:.0f} days).", dividend_period_multiplier 