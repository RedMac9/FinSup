# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands must be run from the repo root (`FinSup/`) with the virtual environment activated.

```bash
# Activate virtualenv (Windows)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the application (interactive menu)
python app/main.py

# Run with a specific procedure directly
python app/main.py 4

# Run exchange rate integration tests
python app/services/exchange_rate.py

# Run ETF validation test
python app/tests/validate_etf.py
```

The app runs from `FinRep2/` as the working directory — all relative paths (secrets, CSVs) resolve from there.

## Architecture

**Entry point**: `app/main.py` — presents a numbered menu and routes to one of these procedures:

| # | Description |
|---|---|
| 1 | GPW (Warsaw Stock Exchange) → Google Sheets |
| 2 | S&P 500 → Google Sheets |
| 4 | PROD (full pipeline): exchange rates → metrics → PostgreSQL → Google Sheets → Pushbullet |
| 5/6/7/13 | Dash interactive graph (GPW / S&P500 / PROD / ETF) |
| 12 | ETF list → Google Sheets |
| 14 | Exchange rates + DB/Sheets update only (no push notification) |
| 15 | Trade transaction editor (Dash UI) |

**Core data pipeline** (procedure 4 is the canonical full run):
1. `exchange_rate.py` — fetches PLN rates from NBP API, saves to `exchange_rates.csv` and PostgreSQL
2. `tickers_lists/ticker_groups.py` — scrapes tickers dynamically (GPW from biznesradar.pl, S&P500 from Wikipedia)
3. `services/market_metrics.py:metrics_separate_tabs()` — bulk-downloads 6 months of OHLC via `yf.download()`, computes SMA/EMA/ATH metrics for each ticker, saves OHLC to a CSV (`historical_prices_PROD.csv` etc.), returns a flat DataFrame also saved to `final_df_metrics.csv`
4. `services/database_service.py` — upserts metrics into PostgreSQL (`tickers_metrics` table), reads `v_open_positions_metrics` and `v_roi_summary` views
5. `services/google_gsheet.py` — writes DataFrames to Google Sheets (hardcoded `SPREADSHEET_ID`)
6. `services/daily_pushbullet.py` — sends a Pushbullet notification
7. Graphs (procedures 5/6/7/13) — `output/graph.py` launches a Dash server that reads the pre-generated CSV files from step 3

**Database**: PostgreSQL on `psql01.mikr.us`. Key tables: `tickers_metrics` (upserted on ticker+date), `trade_txn`, `exchange_rate`. Key views: `v_open_positions_metrics`, `v_roi_summary`. Schema defined in `database/`.

**Secrets**: `secrets.env` in `FinRep2/` root is loaded via `python-dotenv` by each service that needs DB or API access. Google Sheets auth uses a service account JSON at `secrets/finsup2-proj-90ea4909d4c5.json`.

**Graph/Dash pipeline dependency**: The graph procedures (5/6/7/13) read CSV files that are only generated when the corresponding data procedure (1/2/4/12) has run first. Running procedure 5 without ever running procedure 1 will fail.

**market_config.py**: Maps yfinance exchange codes (`NYQ`, `WSE`, `NMS`, etc.) to TradingView market prefixes used to build chart URLs.

**Notable files to ignore**: `app/services/FULL_MARKETS_*.py` and `app/main_div_toberemoved.py` are legacy/archived scripts not part of the active pipeline.
