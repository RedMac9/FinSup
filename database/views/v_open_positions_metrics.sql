CREATE OR REPLACE VIEW v_open_positions_metrics AS
WITH
-- Step 1: Identify open positions and calculate avg buy price and find the oldest buy date.
open_positions_with_avg_price AS (
    SELECT
        ticker,
        market,
        SUM(CASE WHEN side = 'BUY' THEN gross_amount ELSE 0 END) / SUM(CASE WHEN side = 'BUY' THEN quantity ELSE 0 END) as avg_buy_price,
        MIN(CASE WHEN side = 'BUY' THEN exec_time_utc::date ELSE NULL END) as oldest_buy_date
    FROM trade_txn
    GROUP BY ticker, market
    HAVING SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) > 0
),
-- Step 2: Get the transformed ticker name for joining with the metrics table.
open_positions_transformed AS (
    SELECT
        p.ticker,
        p.market,
        p.avg_buy_price,
        p.oldest_buy_date,
        bt.reason as category,
        CASE
            WHEN mtt.suffix IS NOT NULL THEN p.ticker || mtt.suffix
            ELSE p.ticker
        END AS transformed_ticker
    FROM open_positions_with_avg_price p
    LEFT JOIN market_ticker_transformations mtt ON p.market = mtt.market
    LEFT JOIN blacklisted_tickers bt ON p.ticker = bt.ticker
),
-- Step 3: Get the latest metrics for each of our open positions.
latest_metrics AS (
    SELECT
        tm.ticker as transformed_ticker,
        tm.tradingview_url,
        tm.pct_diff_ath30,
        tm.date,
        tm.pct_change_last,
        tm."DaysCloseAboveEMA32_Last30_",
        tm.close,
        ROW_NUMBER() OVER(PARTITION BY tm.ticker ORDER BY tm.date DESC) as rn
    FROM tickers_metrics tm
    WHERE tm.ticker IN (SELECT transformed_ticker FROM open_positions_transformed)
),
-- Step 4: Aggregate comments
comments_agg AS (
    SELECT
        ticker,
        market,
        (ARRAY_AGG(TO_CHAR(date, 'YYYY-MM-DD') || ': ' || comment ORDER BY date DESC))[1] as recent_comment,
        STRING_AGG(TO_CHAR(date, 'YYYY-MM-DD') || ': ' || comment, ' | ' ORDER BY date DESC) as all_comments
    FROM tickers_comment
    GROUP BY ticker, market
)
-- Step 5: Join and calculate final metrics.
SELECT
    lm.tradingview_url,
    opt.ticker, -- original ticker
    ROUND(
        ((lm.close - opt.avg_buy_price) / NULLIF(opt.avg_buy_price, 0) * 100)::numeric,
        2
    ) AS pct_diff_from_avg_buy,
    ROUND((lm.pct_diff_ath30)::numeric, 2) as pct_diff_ath30,
    ROUND((lm.pct_change_last)::numeric, 2) as pct_change_last,
    lm."DaysCloseAboveEMA32_Last30_",
    (CURRENT_DATE - opt.oldest_buy_date) as days_in_wallet,
    opt.category,
    lm.date,
    ca.recent_comment,
    ca.all_comments
FROM
    open_positions_transformed opt
JOIN
    latest_metrics lm ON opt.transformed_ticker = lm.transformed_ticker
LEFT JOIN
    comments_agg ca ON opt.ticker = ca.ticker AND opt.market = ca.market
WHERE
    lm.rn = 1
ORDER BY
    CASE
        WHEN opt.category = 'REIT' THEN 1
        ELSE 0
    END,
    pct_diff_ath30 ASC;
