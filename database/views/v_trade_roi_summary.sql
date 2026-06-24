CREATE OR REPLACE VIEW v_trade_roi_summary AS
WITH base AS (
  SELECT
    ticker,
    currency,
    side,
    exec_time_utc::timestamp AS exec_ts,
    quantity::numeric        AS qty,
    gross_amount::numeric    AS gross_amt
  FROM trade_txn
),
-- Aggregate buys and sells per ticker with first/last dates to support filters/dates
agg AS (
  SELECT
    ticker,
    currency,
    SUM(CASE WHEN side = 'BUY'  THEN qty       ELSE 0 END) AS buy_qty,
    SUM(CASE WHEN side = 'SELL' THEN qty       ELSE 0 END) AS sold_qty,
    SUM(CASE WHEN side = 'BUY'  THEN gross_amt ELSE 0 END) AS buy_gross_amt,
    SUM(CASE WHEN side = 'SELL' THEN gross_amt ELSE 0 END) AS sell_gross_amt,
    MIN(CASE WHEN side = 'BUY'  THEN exec_ts END)          AS first_buy_dt,
    MAX(CASE WHEN side = 'BUY'  THEN exec_ts END)          AS last_buy_dt,
    MIN(CASE WHEN side = 'SELL' THEN exec_ts END)          AS first_sell_dt,
    MAX(CASE WHEN side = 'SELL' THEN exec_ts END)          AS last_sell_dt
  FROM base
  GROUP BY ticker, currency
),
-- Enforce sell_date > buy_date at the aggregate level:
-- choose the earliest sell strictly after the earliest buy as sell_date,
-- and the earliest buy as buy_date when buys exist.
dates AS (
  SELECT
    a.ticker,
    a.currency,
    a.buy_qty,
    a.sold_qty,
    a.buy_gross_amt,
    a.sell_gross_amt,
    -- open quantity can be negative by request
    (a.buy_qty - a.sold_qty) AS open_qty,
    -- buy_date defined as the earliest buy
    a.first_buy_dt           AS buy_date,
    -- sell_date must be strictly greater than buy_date; if no such sell exists, keep NULL
    CASE
      WHEN a.first_buy_dt IS NOT NULL AND a.first_sell_dt IS NOT NULL AND a.last_sell_dt > a.first_buy_dt
        THEN a.first_sell_dt
      ELSE NULL
    END                      AS sell_date
  FROM agg a
),
-- ROI and ROI% computed from gross amounts, only when sell_date > buy_date holds
calc AS (
  SELECT
    d.ticker,
    d.currency,
    d.buy_qty,
    d.sold_qty,
    d.open_qty,
    d.buy_date,
    d.sell_date,
    CASE
      WHEN d.sell_date IS NOT NULL AND d.buy_qty > 0
        THEN (d.sell_gross_amt - d.buy_gross_amt)
      ELSE NULL
    END AS roi,
    CASE
      WHEN d.sell_date IS NOT NULL AND d.buy_gross_amt <> 0
        THEN ((d.sell_gross_amt - d.buy_gross_amt) / d.buy_gross_amt) * 100
      ELSE NULL
    END AS roi_pct
  FROM dates d
)
SELECT
  ticker,
  buy_qty,
  sold_qty,
  open_qty,
  roi_pct,
  roi,
  currency,
  buy_date,
  sell_date
FROM calc
ORDER BY buy_date desc, ticker, currency;