CREATE OR REPLACE VIEW v_daily_trading_statistics AS
WITH
-- Step 1: Calculate average buy price for all currently open positions.
open_positions_avg_price AS (
    SELECT
        ticker,
        market,
        SUM(CASE WHEN side = 'BUY' THEN gross_amount ELSE 0 END) / NULLIF(SUM(CASE WHEN side = 'BUY' THEN quantity ELSE 0 END), 0) as avg_buy_price
    FROM
        trade_txn
    GROUP BY
        ticker, market
    HAVING
        SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) > 0
),

-- Step 2: Create the transformed ticker to match the metrics table.
open_positions_transformed AS (
    SELECT
        op.ticker,
        op.market,
        op.avg_buy_price,
        CASE
            WHEN mtt.suffix IS NOT NULL THEN op.ticker || mtt.suffix
            ELSE op.ticker
        END AS transformed_ticker
    FROM
        open_positions_avg_price op
    LEFT JOIN
        market_ticker_transformations mtt ON op.market = mtt.market
)

-- Step 3: Join with daily metrics and calculate the daily percentage difference.
SELECT
    opt.ticker, -- Original ticker
    tm.date,
    tm.close,
    opt.avg_buy_price,
    ROUND(
        (((tm.close - opt.avg_buy_price) / NULLIF(opt.avg_buy_price, 0)) * 100)::numeric,
        2
    ) AS pct_diff_from_avg_buy
FROM
    tickers_metrics tm
JOIN
    open_positions_transformed opt ON tm.ticker = opt.transformed_ticker
ORDER BY
    opt.ticker, tm.date;
