CREATE TABLE tickers_comment (
    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(64) NOT NULL,
    comment TEXT NOT NULL,
    date DATE NOT NULL,
    PRIMARY KEY (ticker, market, comment, date)
);
