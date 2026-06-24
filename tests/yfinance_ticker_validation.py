import yfinance as yf

import pandas as pd

def validate_tickers(ticker_list, description):
    """Attempts to download data for a list of tickers and reports on success/failure."""
    print(f"--- {description} ---")
    
    # Attempt to download data
    data = yf.download(ticker_list, period="1mo", group_by='ticker')
    
    # Check for errors (yfinance often prints errors but doesn't raise exceptions for individual tickers)
    if data.empty:
        print("Download failed for all tickers in this list.")
        return

    print("Download results:")
    for ticker in ticker_list:
        # A successful download will have a non-empty DataFrame for the ticker's key.
        # For single tickers, the columns aren't nested, so we check that too.
        if isinstance(data.columns, pd.MultiIndex): # Multiple tickers
             if ticker in data and not data[ticker].empty:
                print(f"  [SUCCESS] {ticker}")
             else:
                print(f"  [FAILED]  {ticker}")
        else: # Single ticker
            if not data.empty:
                 print(f"  [SUCCESS] {ticker}")
            else:
                 print(f"  [FAILED]  {ticker}")


# List 1: User's original tickers
original_tickers = ["LQDE", "XCS6", "XCHA", "AHYQ", "XUTC", "IUAA", "XDEM"]
validate_tickers(original_tickers, "Testing Original Tickers (no exchange suffix)")

print("\n" + "="*40 + "\n")

# List 2: Corrected tickers with exchange suffixes
# Note: IUAA is excluded as it was not found.
corrected_tickers = ["LQDE.L", "XCS6.DE", "XCHA.L", "AHYQ.DE", "XUTC.DE", "XDEM.DE"]
validate_tickers(corrected_tickers, "Testing Corrected Tickers (with exchange suffix)")
