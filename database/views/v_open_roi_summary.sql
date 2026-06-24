CREATE OR REPLACE VIEW v_open_roi_summary AS
WITH
-- Step 1: Calculate cost basis and quantity for all currently open positions, excluding blacklisted tickers.
open_positions AS (
    SELECT
        ticker,
        market,
        currency,
        SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS open_quantity,
        (SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END)) * 
        (SUM(CASE WHEN side = 'BUY' THEN gross_amount ELSE 0 END) / NULLIF(SUM(CASE WHEN side = 'BUY' THEN quantity ELSE 0 END), 0)) AS cost_basis
    FROM
        trade_txn
    WHERE
        ticker NOT IN (SELECT ticker FROM blacklisted_tickers) -- Exclude blacklisted tickers
    GROUP BY
        ticker, market, currency
    HAVING
        SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) > 0
),

-- Step 2: Get the historical daily rate for each currency to calculate daily values.
daily_rates AS (
    SELECT
        d.date,
        c.currency,
        CASE
            WHEN c.currency = 'PLN' THEN 1
            ELSE COALESCE(er.rate, 100000000000000.0)
        END AS rate_to_pln
    FROM
        (SELECT DISTINCT date FROM tickers_metrics) d
    CROSS JOIN
        (SELECT DISTINCT currency FROM open_positions) c
    LEFT JOIN LATERAL (
        SELECT rate
        FROM exchange_rate er
        WHERE er.currency = c.currency AND er.date <= d.date AND er.quote = 'PLN'
        ORDER BY er.date DESC
        LIMIT 1
    ) er ON TRUE
),

-- Step 3: Calculate daily values, using the historical daily rate for all calculations.
positions_daily_value AS (
    SELECT
        d.date,
        op.ticker,
        -- Cost Basis: Converted to PLN using the HISTORICAL rate for that specific day.
        ROUND((op.cost_basis * dr.rate_to_pln)::numeric, 2) AS cost_basis_pln,
        -- Current Value: Converted to PLN using the HISTORICAL rate for that specific day.
        ROUND((op.open_quantity * tm.close * dr.rate_to_pln)::numeric, 2) AS current_value_pln
    FROM
        (SELECT DISTINCT date FROM tickers_metrics) d
    CROSS JOIN
        open_positions op
    JOIN
        daily_rates dr ON d.date = dr.date AND op.currency = dr.currency
    LEFT JOIN
        market_ticker_transformations mtt ON op.market = mtt.market
    LEFT JOIN
        tickers_metrics tm ON tm.date = d.date AND tm.ticker = (CASE WHEN mtt.suffix IS NOT NULL THEN op.ticker || mtt.suffix ELSE op.ticker END)
    WHERE
        tm.close IS NOT NULL
)

-- Step 4: Aggregate all position values for each day to get the total portfolio ROI.
SELECT
    pdv.date,
    ROUND(SUM(pdv.current_value_pln)::numeric, 2) AS total_value_pln,
    ROUND(SUM(pdv.cost_basis_pln)::numeric, 2) AS total_cost_basis_pln,
    ROUND((SUM(pdv.current_value_pln) - SUM(pdv.cost_basis_pln))::numeric, 2) AS roi_pln,
    ROUND(
        (((SUM(pdv.current_value_pln) / NULLIF(SUM(pdv.cost_basis_pln), 0)) - 1) * 100)::numeric,
        2
    ) AS roi_pct
FROM
    positions_daily_value pdv
GROUP BY
    pdv.date
ORDER BY
    pdv.date DESC;