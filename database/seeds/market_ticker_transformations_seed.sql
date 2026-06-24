INSERT INTO market_ticker_transformations (market, suffix, market_yfinance, note) VALUES
('GPW', '.WA', 'WSE', NULL),
('LSE', '.L', 'LSE', 'London'),
('MIL', '.DE', 'GER', 'XETRA'),
('NYSE', NULL, 'NYQ', NULL),
('NASDAQ', NULL, 'NMS', NULL)
ON CONFLICT (market) DO UPDATE SET
    suffix = EXCLUDED.suffix,
    market_yfinance = EXCLUDED.market_yfinance,
    note = EXCLUDED.note;