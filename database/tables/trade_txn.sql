DROP TABLE trade_txn;

CREATE TABLE trade_txn (
	txn_id bigserial NOT NULL,
	ticker varchar(10) NOT NULL,
	market varchar(64) NOT NULL,
	side varchar(4) NOT NULL,
	exec_time_utc timestamptz NOT NULL,
	currency bpchar(5) NOT NULL,
	broker varchar(32) NOT NULL,
	portfolio varchar(64) NULL,
	quantity numeric(20, 8) NULL,
	price numeric(20, 8) NULL,
	gross_amount numeric(28, 8) NULL,
	fee numeric(20, 8) DEFAULT 0 NOT NULL,
	tax numeric(20, 8) DEFAULT 0 NOT NULL,
	other_cost numeric(20, 8) DEFAULT 0 NOT NULL,
	broker_txn_id varchar(32),
	note varchar(64),
	CONSTRAINT ck_gross_pos CHECK (((gross_amount IS NULL) OR (gross_amount > (0)::numeric))),
	CONSTRAINT ck_price_pos CHECK (((price IS NULL) OR (price > (0)::numeric))),
	CONSTRAINT ck_qty_pos CHECK (((quantity IS NULL) OR (quantity > (0)::numeric))),
	CONSTRAINT trade_txn_currency_check CHECK ((currency = ANY (ARRAY['PLN'::bpchar, 'USD'::bpchar, 'CAD'::bpchar, 'EUR'::bpchar, 'CHF'::bpchar, 'GBP'::bpchar, 'JPY'::bpchar]))),
	CONSTRAINT trade_txn_pkey PRIMARY KEY (txn_id),
	CONSTRAINT trade_txn_side_check CHECK (((side)::text = ANY ((ARRAY['BUY'::character varying, 'SELL'::character varying])::text[])))
);
CREATE INDEX ix_trade_txn_market_time ON trade_txn USING btree (market, exec_time_utc);
CREATE INDEX ix_trade_txn_portfolio_time ON trade_txn USING btree (portfolio, exec_time_utc);
CREATE INDEX ix_trade_txn_side_time ON trade_txn USING btree (side, exec_time_utc);
CREATE INDEX ix_trade_txn_ticker_time ON trade_txn USING btree (ticker, exec_time_utc);





------------

BEGIN;

-- 1) Create or replace the function (safe even if exists)
CREATE OR REPLACE FUNCTION trg_trade_txn_amounts()
RETURNS trigger AS $$
DECLARE
  nulls_count int;
BEGIN
  nulls_count :=
    (CASE WHEN NEW.quantity     IS NULL THEN 1 ELSE 0 END) +
    (CASE WHEN NEW.price        IS NULL THEN 1 ELSE 0 END) +
    (CASE WHEN NEW.gross_amount IS NULL THEN 1 ELSE 0 END);

  IF nulls_count <> 1 THEN
    RAISE EXCEPTION 'Exactly one of (quantity, price, gross_amount) must be NULL on input; got %', nulls_count;
  END IF;

  IF NEW.quantity IS NULL THEN
    IF NEW.price IS NULL OR NEW.gross_amount IS NULL THEN
      RAISE EXCEPTION 'Need price and gross_amount to compute quantity';
    END IF;
    IF NEW.price = 0 THEN
      RAISE EXCEPTION 'Price cannot be zero';
    END IF;
    NEW.quantity := NEW.gross_amount / NEW.price;

  ELSIF NEW.price IS NULL THEN
    IF NEW.quantity IS NULL OR NEW.gross_amount IS NULL THEN
      RAISE EXCEPTION 'Need quantity and gross_amount to compute price';
    END IF;
    IF NEW.quantity = 0 THEN
      RAISE EXCEPTION 'Quantity cannot be zero';
    END IF;
    NEW.price := NEW.gross_amount / NEW.quantity;

  ELSE
    IF NEW.quantity IS NULL OR NEW.price IS NULL THEN
      RAISE EXCEPTION 'Need quantity and price to compute gross_amount';
    END IF;
    NEW.gross_amount := NEW.quantity * NEW.price;
  END IF;

  NEW.quantity := ROUND(NEW.quantity, 8);
  NEW.price := ROUND(NEW.price, 8);
  NEW.gross_amount := ROUND(NEW.gross_amount, 8);

  IF NEW.quantity <= 0 OR NEW.price <= 0 OR NEW.gross_amount <= 0 THEN
    RAISE EXCEPTION 'All of quantity, price, gross_amount must be positive after computation';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2) Drop trigger if it exists (harmless if not)
DROP TRIGGER IF EXISTS trg_bi_trade_txn_amounts ON trade_txn;

-- 3) Create trigger
CREATE TRIGGER trg_bi_trade_txn_amounts
BEFORE INSERT OR UPDATE ON trade_txn
FOR EACH ROW
EXECUTE FUNCTION trg_trade_txn_amounts();

COMMIT;
