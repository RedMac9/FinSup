-- WARNING: This script will permanently delete all data in the 'exchange_rate' table before rebuilding it.
-- It adjusts the UNIQUE constraint to match the application code's ON CONFLICT clause.

-- Drop the table to ensure a clean rebuild
DROP TABLE IF EXISTS exchange_rate CASCADE;

-- Recreate the table with the corrected UNIQUE constraint
CREATE TABLE exchange_rate (
  id         BIGSERIAL PRIMARY KEY,
  date       DATE             NOT NULL,
  currency   CHAR(3)          NOT NULL,
  rate       NUMERIC(20,10)   NOT NULL,
  source     VARCHAR(16)      DEFAULT 'NBP',
  quote      CHAR(3)          DEFAULT 'PLN', -- This column remains for context
  created_at TIMESTAMPTZ      DEFAULT now(),
  -- Corrected constraint to match ON CONFLICT(date, currency)
  CONSTRAINT ux_exchange_rate UNIQUE (date, currency),
  CONSTRAINT ck_currency_alpha3 CHECK (currency ~ '^[A-Z]{3}$' OR currency = 'PLN'),
  CONSTRAINT ck_quote_alpha3 CHECK (quote ~ '^[A-Z]{3}$' OR quote = 'PLN'),
  CONSTRAINT ck_rate_positive CHECK (rate > 0)
);

-- Recreate indexes
CREATE INDEX ix_exchange_rate_date ON exchange_rate(date);
CREATE INDEX ix_exchange_rate_currency_date ON exchange_rate(currency, date);
CREATE INDEX ix_exchange_rate_usd ON exchange_rate(date) WHERE currency = 'USD';
