import yfinance as yf

# Define the ticker symbol
ticker_symbol = "BBT.WA"

# Create a Ticker object
ticker = yf.Ticker(ticker_symbol)

# Get the latest historical data (last available trading day)
# Using period="1d" might not always give the most recent *closed* price
# if queried during market hours or on a non-trading day.
# A more robust way to get the very last closing price from available data
# is to fetch a slightly longer period and take the last entry, or rely on 'info' if up-to-date.
# However, for the last trading day's close, period="1d" is usually sufficient.
# For a more reliable "previous close" often "2d" then taking iloc[-1] or iloc[-2] depending on timing,
# or using ticker.info['previousClose'] is better.
# Given the typical use case and simplicity, period="1d" is common.
data = ticker.history(period="6mo")

# Extract the latest close price
if not data.empty:
    latest_close_price = data['Close'].iloc[-1]
    close_prices = data['Close']
    ath10 = close_prices.rolling(window=10).max()
    ath30 = close_prices.rolling(window=30).max()
    print(latest_close_price)
    print(ath10)
    print(ath30)
else:
    print(f"No data found for {ticker_symbol} for the last day.")
    # Fallback or error handling:
    # You could try to get 'previousClose' from ticker.info
    # info = ticker.info
    # if 'previousClose' in info and info['previousClose'] is not None:
    #     latest_close_price = info['previousClose']
    #     print(f"Using previousClose from info: {latest_close_price}")
    # else:
    #     print("Could not retrieve previous close price from info either.")