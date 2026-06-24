import yfinance as yf

tickers = ['AEGE', 'IBB1', 'EUN5', 'INAA', 'GLDV', 'PHAG', 'VVSM', 'CEU1', 'IWFV', 'S']

print("--- Checking Ticker Validity ---")
for ticker in tickers:
    data = yf.download(ticker, period="1d", progress=False)
    if data.empty:
        print(f"'{ticker}': INVALID (No data returned)")
    else:
        print(f"'{ticker}': VALID")
print("--- Check Complete ---")