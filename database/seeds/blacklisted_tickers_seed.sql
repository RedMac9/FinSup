INSERT INTO blacklisted_tickers (ticker, reason, note) VALUES
('CHMI', 'REIT', NULL),
('DOC', 'REIT', NULL),
('TWO', 'REIT', NULL),
('IVR', 'REIT', NULL),
('BXMT', 'REIT', NULL),
('ACRE', 'REIT', NULL),
('TRTX', 'REIT', NULL),
('ORC', 'REIT', NULL),
('DX', 'REIT', NULL),
('RC', 'REIT', NULL),
('ARR', 'REIT', NULL)
ON CONFLICT (ticker) DO NOTHING;
