CREATE OR REPLACE VIEW v_roi AS
WITH latest_date AS (
    SELECT MAX(date) AS max_date
    FROM tickers_metrics
),

open_positions AS (
    SELECT
        ticker,
        market,
        currency,
        SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS open_quantity,
        SUM(CASE WHEN side = 'BUY' THEN gross_amount ELSE 0 END) AS cost_basis,
        MIN(exec_time_utc)::date AS buy_date
    FROM trade_txn
    WHERE ticker NOT IN (SELECT ticker FROM blacklisted_tickers)
    GROUP BY ticker, market, currency
    HAVING SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) > 0
),

open_positions_roi AS (
    SELECT
        op.ticker,
        'open' AS position_status,
        op.cost_basis,
        op.open_quantity * tm.close AS current_value,
        op.currency,
        op.buy_date,
        NULL::date AS close_date,
        (ld.max_date - op.buy_date) AS days_in_wallet,
        (op.open_quantity * tm.close - op.cost_basis) AS roi_original_currency,
        (((op.open_quantity * tm.close) / op.cost_basis) - 1) * 100 AS roi_pct,
        (op.open_quantity * tm.close - op.cost_basis) * COALESCE(er.rate, 1) AS roi_pln
    FROM open_positions op
    JOIN latest_date ld ON 1=1
    LEFT JOIN market_ticker_transformations mtt ON op.market = mtt.market
    JOIN tickers_metrics tm ON tm.ticker = (CASE WHEN mtt.suffix IS NOT NULL THEN op.ticker || mtt.suffix ELSE op.ticker END) AND tm.date = ld.max_date
    LEFT JOIN LATERAL (
        SELECT rate
        FROM exchange_rate er
        WHERE er.currency = op.currency AND er.quote = 'PLN' AND er.date <= ld.max_date
        ORDER BY er.date DESC
        LIMIT 1
    ) er ON TRUE
),

closed_positions AS (
    SELECT
        ticker,
        market,
        currency,
        SUM(CASE WHEN side = 'BUY' THEN gross_amount ELSE 0 END) AS cost_basis,
        SUM(CASE WHEN side = 'SELL' THEN gross_amount ELSE 0 END) AS proceeds,
        MIN(exec_time_utc)::date AS buy_date,
        MAX(exec_time_utc)::date AS close_date
    FROM trade_txn
    GROUP BY ticker, market, currency
    HAVING SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) = 0
),

closed_positions_roi AS (
    SELECT
        cp.ticker,
        'closed' AS position_status,
        cp.cost_basis,
        cp.proceeds AS current_value,
        cp.currency,
        cp.buy_date,
        cp.close_date,
        (cp.close_date - cp.buy_date) AS days_in_wallet,
        (cp.proceeds - cp.cost_basis) AS roi_original_currency,
        ((cp.proceeds / cp.cost_basis) - 1) * 100 AS roi_pct,
        (cp.proceeds - cp.cost_basis) * COALESCE(
            CASE
                WHEN cp.currency = 'PLN' THEN 1
                WHEN past_rate.date IS NULL AND future_rate.date IS NULL THEN 1
                WHEN past_rate.date IS NULL THEN future_rate.rate
                WHEN future_rate.date IS NULL THEN past_rate.rate
                WHEN (cp.close_date - past_rate.date) <= (future_rate.date - cp.close_date) THEN past_rate.rate
                ELSE future_rate.rate
            END, 1
        ) AS roi_pln
    FROM closed_positions cp
    LEFT JOIN LATERAL (
        SELECT rate, date
        FROM exchange_rate er
        WHERE er.currency = cp.currency AND er.date <= cp.close_date AND er.quote = 'PLN'
        ORDER BY er.date DESC
        LIMIT 1
    ) past_rate ON TRUE
    LEFT JOIN LATERAL (
        SELECT rate, date
        FROM exchange_rate er
        WHERE er.currency = cp.currency AND er.date > cp.close_date AND er.quote = 'PLN'
        ORDER BY er.date ASC
        LIMIT 1
    ) future_rate ON TRUE
),

unioned_roi AS (
    SELECT
        ticker,
        position_status,
        roi_pct,
        roi_original_currency,
        currency,
        roi_pln,
        buy_date,
        close_date,
        days_in_wallet
    FROM open_positions_roi
    UNION ALL
    SELECT
        ticker,
        position_status,
        roi_pct,
        roi_original_currency,
        currency,
        roi_pln,
        buy_date,
        close_date,
        days_in_wallet
    FROM closed_positions_roi
)

SELECT
    ticker,
    position_status,
    ROUND(roi_pct::numeric, 2) AS roi_pct,
    ROUND(roi_original_currency::numeric, 2) AS roi_original_currency,
    currency,
    ROUND(roi_pln::numeric, 2) AS roi_pln,
    buy_date,
    close_date,
    days_in_wallet
FROM unioned_roi;
