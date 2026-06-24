CREATE OR REPLACE VIEW v_roi_summary AS
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
            ELSE COALESCE(er.rate, 10000000)
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
),

-- Step 4: Aggregate all position values for each day to get the total portfolio ROI.
open_roi as (
    SELECT
        pdv.date,
        ROUND(SUM(pdv.current_value_pln)::numeric, 2) AS open_total_value_pln,
        ROUND(SUM(pdv.cost_basis_pln)::numeric, 2) AS open_total_cost_basis_pln,
        ROUND((SUM(pdv.current_value_pln) - SUM(pdv.cost_basis_pln))::numeric, 2) AS open_roi_pln,
        ROUND(
            (((SUM(pdv.current_value_pln) / NULLIF(SUM(pdv.cost_basis_pln), 0)) - 1) * 100)::numeric,
            2
        ) AS open_roi_pct
    FROM
        positions_daily_value pdv
    GROUP BY
        pdv.date
),

-- Step 5: Identify trades that were closed in 2025.
closed_trades_2025 AS (
    SELECT
        ticker,
        market,
        currency,
        MAX(exec_time_utc::date) as closing_date -- The date of the last trade is the closing date
    FROM
        trade_txn
    GROUP BY
        ticker, market, currency
    HAVING
        SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) = 0 AND
        EXTRACT(YEAR FROM MAX(exec_time_utc)) = 2025
),

-- Step 6: Get all transactions for the closed trades.
closed_trade_txns AS (
    SELECT
        t.*,
        ct.closing_date
    FROM
        trade_txn t
    JOIN
        closed_trades_2025 ct ON t.ticker = ct.ticker AND t.market = ct.market AND t.currency = ct.currency
),

-- Step 7: Calculate cost basis and proceeds for each closed trade.
closed_positions_summary AS (
    SELECT
        ticker,
        market,
        currency,
        closing_date,
        SUM(CASE WHEN side = 'BUY' THEN gross_amount ELSE 0 END) AS cost_basis,
        SUM(CASE WHEN side = 'SELL' THEN gross_amount ELSE 0 END) AS proceeds
    FROM
        closed_trade_txns
    GROUP BY
        ticker, market, currency, closing_date
),

-- Step 8: Get the closest exchange rate at the closing date.
closing_date_rates AS (
    SELECT
        cps.ticker,
        cps.currency,
        CASE
            WHEN cps.currency = 'PLN' THEN 1
            WHEN past_rate.date IS NULL AND future_rate.date IS NULL THEN 10000000
            WHEN past_rate.date IS NULL THEN future_rate.rate
            WHEN future_rate.date IS NULL THEN past_rate.rate
            WHEN (cps.closing_date - past_rate.date) <= (future_rate.date - cps.closing_date) THEN past_rate.rate
            ELSE future_rate.rate
        END AS rate_to_pln
    FROM
        closed_positions_summary cps
    -- Find the closest rate on or before the closing date.
    LEFT JOIN LATERAL (
        SELECT rate, date
        FROM exchange_rate er
        WHERE er.currency = cps.currency AND er.date <= cps.closing_date AND er.quote = 'PLN'
        ORDER BY er.date DESC
        LIMIT 1
    ) past_rate ON TRUE
    -- Find the closest rate after the closing date.
    LEFT JOIN LATERAL (
        SELECT rate, date
        FROM exchange_rate er
        WHERE er.currency = cps.currency AND er.date > cps.closing_date AND er.quote = 'PLN'
        ORDER BY er.date ASC
        LIMIT 1
    ) future_rate ON TRUE
),

-- Step 9: Calculate ROI in PLN.
closed_positions_roi AS (
    SELECT
        cps.ticker,
        ROUND((cps.cost_basis * cdr.rate_to_pln)::numeric, 2) AS cost_basis_pln,
        ROUND((cps.proceeds * cdr.rate_to_pln)::numeric, 2) AS proceeds_pln
    FROM
        closed_positions_summary cps
    JOIN
        closing_date_rates cdr ON cps.ticker = cdr.ticker
),

-- Step 10: Aggregate all closed position values.
closed_roi_2025 as (
    SELECT
        ROUND(SUM(cpr.proceeds_pln)::numeric, 2) AS closed2025_total_proceeds_pln,
        ROUND(SUM(cpr.cost_basis_pln)::numeric, 2) AS closed2025_total_cost_basis_pln,
        ROUND((SUM(cpr.proceeds_pln) - SUM(cpr.cost_basis_pln))::numeric, 2) AS closed2025_roi_pln,
        ROUND(
            (((SUM(cpr.proceeds_pln) / NULLIF(SUM(cpr.cost_basis_pln), 0)) - 1) * 100)::numeric,
            2
        ) AS closed2025_roi_pct
    FROM
        closed_positions_roi cpr
)

-- Step 11: Combine open and closed ROI
SELECT
    d.date,
    o.open_total_value_pln,
    o.open_total_cost_basis_pln,
    o.open_roi_pln,
    o.open_roi_pct,
    c.closed2025_total_proceeds_pln,
    c.closed2025_total_cost_basis_pln,
    c.closed2025_roi_pln,
    c.closed2025_roi_pct,
    -- Summed columns
    ROUND((o.open_total_value_pln + c.closed2025_total_proceeds_pln)::numeric, 2) AS total_value_pln,
    ROUND((o.open_total_cost_basis_pln + c.closed2025_total_cost_basis_pln)::numeric, 2) AS total_cost_basis_pln,
    ROUND((o.open_roi_pln + c.closed2025_roi_pln)::numeric, 2) AS total_roi_pln,
    ROUND(
        ((((o.open_total_value_pln + c.closed2025_total_proceeds_pln) / NULLIF(o.open_total_cost_basis_pln + c.closed2025_total_cost_basis_pln, 0)) - 1) * 100)::numeric,
        2
    ) AS total_roi_pct
FROM
    (SELECT DISTINCT date FROM tickers_metrics) d
LEFT JOIN
    open_roi o ON d.date = o.date
CROSS JOIN
    closed_roi_2025 c
ORDER BY
    d.date DESC;