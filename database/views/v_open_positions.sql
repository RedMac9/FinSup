CREATE OR REPLACE VIEW v_open_positions AS
WITH open_quantities AS (
    SELECT
        txn.ticker,
        txn.market,
        SUM(CASE WHEN txn.side = 'BUY'  THEN txn.quantity::numeric ELSE 0 END) -
        SUM(CASE WHEN txn.side = 'SELL' THEN txn.quantity::numeric ELSE 0 END) AS open_qty
    FROM
        trade_txn txn
    GROUP BY
        txn.ticker,
        txn.market
)
SELECT
    CASE
        WHEN mtt.suffix IS NOT NULL THEN oq.ticker || mtt.suffix
        ELSE oq.ticker
    END AS ticker,
    oq.ticker AS ticker_org,
    oq.market
FROM
    open_quantities oq
LEFT JOIN
    market_ticker_transformations mtt ON oq.market = mtt.market
WHERE
    oq.open_qty > 0;