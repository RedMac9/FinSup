CREATE TABLE blacklisted_tickers (
    ticker VARCHAR(20) PRIMARY KEY,
    reason VARCHAR(255),
    note TEXT
);
