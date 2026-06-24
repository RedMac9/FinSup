"""
Tests for currency database functionality.
"""
import sys
import os
import re
import unittest
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Add the project root directory (FinSup2) to the Python path.
# This allows for absolute imports from the 'app' package.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# Use an absolute import from the 'app' package to avoid ambiguity
from services.currency_service import fetch_nbp_table_a_rates, save_rates_to_csv

# Load environment variables from secrets.env located in the app root (FinRep2)
secrets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'secrets.env'))
load_dotenv(secrets_path)

def save_rates_to_db(rates_map, date, target_currencies):
    """
    Saves exchange rates to a PostgreSQL database.

    This function connects to the database using credentials from environment
    variables and performs an 'UPSERT' operation to either insert new rates
    or update existing ones for a specific date.

    Args:
        rates_map (dict): A dictionary mapping currency codes to their rates.
        date (str): The effective date of the rates in 'YYYY-MM-DD' format.
        target_currencies (list): A list of currency codes to save.
    """
    conn = None  # Initialize conn to None
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        print("Successfully connected to the database.")

        with conn.cursor() as cur:
            # Using INSERT ... ON CONFLICT (UPSERT) to avoid duplicates
            # for the same date and currency.
            query = sql.SQL("""
                INSERT INTO {schema}.exchange_rate (date, currency, rate)
                VALUES (%s, %s, %s)
                ON CONFLICT (date, currency) DO UPDATE SET rate = EXCLUDED.rate;
            """).format(schema=sql.Identifier(db_schema))
            for code in target_currencies:
                if code in rates_map:
                    rate = rates_map[code]['mid']
                    cur.execute(query, (date, code, rate))
                    print(f"Upserted: {date} - {code} - {rate:.4f}")

        conn.commit()
        print("Database transaction committed successfully.")

    except psycopg2.Error as error:
        print(f"Database error: {error}")
        if conn:
            conn.rollback() # Roll back the transaction on error
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

def run_exchange_rate_update():
    """
    Fetches latest exchange rates, saves them to CSV, and uploads to the database.
    """
    print("\n--- Fetching Latest Exchange Rates ---")
    rates, effective_date = fetch_nbp_table_a_rates()
    
    if rates:
        target_currencies_list = ['USD', 'CAD', 'EUR', 'CHF', 'GBP', 'JPY']

        print("\n--- Generating Exchange Rate CSV File ---")
        save_rates_to_csv("exchange_rates.csv", rates_map=rates, effective_date=effective_date, target_currencies=target_currencies_list)
        
        print("\n--- Uploading Rates to PostgreSQL Database ---")
        save_rates_to_db(rates, effective_date, target_currencies=target_currencies_list)
    else:
        print("Could not fetch exchange rates. Skipping CSV generation and DB upload.")

class TestCurrencyService(unittest.TestCase):

    def test_fetch_real_nbp_table_a_rates(self):
        """
        Integration test: Fetches live data from the NBP API and validates its structure.
        """
        # Act: Call the function
        rates_map, date = fetch_nbp_table_a_rates()

        # Assert: Validate the structure and types of the live data
        self.assertIsNotNone(rates_map, "The rates dictionary should not be None.")
        self.assertIsInstance(rates_map, dict, "The returned rates should be a dictionary.")
        self.assertIsInstance(date, str, "The returned date should be a string.")
        self.assertTrue(re.match(r'\d{4}-\d{2}-\d{2}', date), "Date should be in YYYY-MM-DD format.")

        print(f"\n--- Live NBP Data for {date} ---")
        
        target_currencies = ['USD', 'CAD', 'EUR', 'CHF', 'GBP', 'JPY']
        for code in target_currencies:
            self.assertIn(code, rates_map, f"Currency code '{code}' should be in the rates map.")
            rate_info = rates_map[code]
            self.assertIsInstance(rate_info, dict)
            self.assertIn('mid', rate_info)
            self.assertIsInstance(rate_info['mid'], float, f"The 'mid' rate for {code} should be a float.")
            print(f"{code}: {rate_info['mid']:.4f}")

if __name__ == '__main__':
    run_exchange_rate_update()
    print("-" * 40)
    # --- Running Unit Tests ---
    unittest.main(argv=['first-arg-is-ignored'], exit=False)