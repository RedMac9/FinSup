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
    nasdaq_tickers = get_nasdaq_tickers()

    for ticker in nasdaq_tickers:
        print(f"Processing {ticker}...")
        try:


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

            market_cap = ticker.info.get("marketCap")
            avg_volume = ticker.info.get("averageVolume")
            sector  = ticker.info.get("sector") 
            industry  = ticker.info.get("industry") 
            current_price = ticker.info.get('currentPrice')
        
            if current_price is None:
                raise ValueError(f"Current price not available for {ticker}")

            if dividends.empty:
                    dividend_period_multiplier = 1
                    return f"No dividend history available for {ticker}.", dividend_period_multiplier 
        
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
        
        except Exception as e:
            raise RuntimeError(f"Failed to fetch dividend data for {ticker}: {e}")
    
        
    return ticker, median_dividend, market_cap, avg_volume, sector, industry, current_price



