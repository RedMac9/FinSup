# Import necessary libraries
import yfinance as yf
import numpy as np

# Define a test ticker symbol (e.g., Apple Inc.)
ticker_symbol = "ALB"

# Create a Ticker object
ticker = yf.Ticker(ticker_symbol)

# Fetch stock information
print("Stock Info:")
print(ticker.info)  # Retrieves general information about the stock

# Fetch historical market data
print("\nHistorical Data:")
historical_data = ticker.history(period="1mo")  # Fetches one month of historical data
print(historical_data)

# Fetch dividends and splits
print("\nDividends:")
dividends = ticker.dividends  # Retrieves dividend history
print(dividends)

print("\nSplits:")
print(ticker.splits)  # Retrieves stock split history

# Test downloading historical data directly
print("\nDownloading Historical Data:")
data = yf.download(ticker_symbol, start="2025-01-01", end="2025-03-01")
print(data)

# Calculate dividends from the last 12 months and their statistics
print("\nDividends from Last 12 Months:")

# Filter dividends from the last 12 months
last_12_months_dividends = dividends[dividends.index >= "2024-03-01"]
print(last_12_months_dividends)

# Check if there are dividends in the last 12 months
if not last_12_months_dividends.empty:
    # Calculate median and average dividend values
    median_dividend = np.median(last_12_months_dividends.values)
    average_dividend = np.mean(last_12_months_dividends.values)
    
    print(f"\nMedian Dividend: {median_dividend}")
    print(f"Average Dividend: {average_dividend}")
else:
    print("\nNo dividends found in the last 12 months.")

# Extract market cap and average volume
print(ticker.info.get("marketCap"))
print(ticker.info.get("averageVolume"))

