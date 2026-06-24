CREATE TABLE market_ticker_transformations (
    market VARCHAR(50) PRIMARY KEY,
    suffix VARCHAR(10),
    market_yfinance VARCHAR(50),
    note VARCHAR(255)
);