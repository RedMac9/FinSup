import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import requests
import json
import pandas as pd
from datetime import datetime
import pytz

# Load environment variables from secrets.env located in the app root (FinRep2)
secrets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'secrets.env'))
load_dotenv(secrets_path)

def get_db_connection():
    """
    Establishes and returns a database connection.
    """
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        return conn
    except psycopg2.Error as error:
        print(f"Database connection error: {error}")
        return None

def get_first_open_position():
    """
    Fetches the first row (ticker, ticker_org, market) from the v_open_positions view.
    Returns a list containing one tuple or an empty list.
    """
    conn = get_db_connection()
    if not conn: return []
    
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        conn.close()
        return []

    try:
        # Select ticker, ticker_org and market from v_open_positions
        query = sql.SQL("SELECT ticker, ticker_org, market FROM {schema}.v_open_positions LIMIT 1").format(
            schema=sql.Identifier(db_schema)
        )

        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            if row:
                return [row] # Return as a list of tuples for consistent iteration
            else:
                print("No open positions found in v_open_positions.")
                return []

    except psycopg2.Error as error:
        print(f"Database error while fetching first open position: {error}")
        return []
    finally:
        conn.close()

def get_all_open_positions():
    """
    Fetches all rows (ticker, ticker_org, market) from the v_open_positions view.
    """
    conn = get_db_connection()
    if not conn: return []
    
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        conn.close()
        return []

    try:
        query = sql.SQL("SELECT ticker, ticker_org, market FROM {schema}.v_open_positions").format(
            schema=sql.Identifier(db_schema)
        )
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()
    except psycopg2.Error as error:
        print(f"Database error while fetching all open positions: {error}")
        return []
    finally:
        conn.close()

def get_negative_positions():
    """
    Fetches rows from v_open_positions filtered by criteria in v_open_positions_metrics.
    Criteria: pct_diff_from_avg_buy < -5 OR pct_diff_ath30 < -5 OR pct_change_last < -5
    """
    conn = get_db_connection()
    if not conn: return []
    
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        conn.close()
        return []

    try:
        # Join v_open_positions and v_open_positions_metrics
        # v_open_positions_metrics.ticker corresponds to v_open_positions.ticker_org
        query = sql.SQL("""
            SELECT t.ticker, t.ticker_org, t.market
            FROM {schema}.v_open_positions t
            JOIN {schema}.v_open_positions_metrics m ON t.ticker_org = m.ticker
            WHERE m.category IS NULL
               AND (m.pct_diff_from_avg_buy < -5
               OR m.pct_diff_ath30 < -5
               OR m.pct_change_last < -5)
        """).format(schema=sql.Identifier(db_schema))
        
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()
    except psycopg2.Error as error:
        print(f"Database error while fetching negative positions: {error}")
        return []
    finally:
        conn.close()

def save_recommendation_to_db(ticker, market, comment):
    """
    Saves the AI recommendation to the tickers_comment table.
    """
    conn = get_db_connection()
    if not conn: return

    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        conn.close()
        return

    # Format date: "2026-01-29 15:30:00+00"
    now = datetime.now(pytz.UTC)
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S+00")

    try:
        query = sql.SQL("""
            INSERT INTO {schema}.tickers_comment (ticker, market, comment, date)
            VALUES (%s, %s, %s, %s)
        """).format(schema=sql.Identifier(db_schema))

        with conn.cursor() as cur:
            cur.execute(query, (ticker, market, comment, formatted_date))
            conn.commit()
            print(f"Successfully saved recommendation for {ticker} to tickers_comment.")

    except psycopg2.Error as error:
        print(f"Database error while saving recommendation: {error}")
        conn.rollback()
    finally:
        conn.close()

def process_ticker(ticker, ticker_org, market):
    """
    Gets recommendation for a single ticker and saves it via OpenRouter API.
    """
    print(f"\nProcessing: {ticker_org} ({market})")
    
    # Define the input prompt
    prompt = f"na podstawie rekomendacji giełdowych i bieżącej analizy wiadomości gospodarczych, przedstaw jedno zdaniowe podsumowanie. Rekomendacja może być trzymaj albo sprzedaj. dla spółki {ticker_org} ({market}). horyzont 1 miesiąc."

    print(f"Requesting AI recommendation from OpenRouter...")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return None

    try:
        # Optimized parameters for concise summary:
        # temperature: 0.1 for deterministic output
        # max_tokens: 150 (safety margin for one sentence)
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/google-gemini/gemini-cli", 
                "X-Title": "FinRep2_Ticker_Recommender", 
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "google/gemini-3.1-flash-lite-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 150
            })
        )
        
        response.raise_for_status()
        data = response.json()
        
        if 'choices' in data and len(data['choices']) > 0:
            recommendation = data['choices'][0]['message']['content'].strip()
            print("Recommendation:")
            print(recommendation)
            
            # Save to database
            save_recommendation_to_db(ticker, market, recommendation)
            
            return recommendation
        else:
            print(f"Error: Unexpected response format from OpenRouter: {data}")
            return None

    except Exception as e:
        print(f"Error getting AI recommendation for {ticker_org}: {e}")
        return None

def main():
    print("Choose an option:")
    print("1. Process only one row (First open position)")
    print("2. Full analysis (All open positions)")
    print("3. Negative companies analysis (Filtered metrics < -5)")
    
    try:
        choice = input("Enter choice (1, 2, or 3): ").strip()
    except EOFError:
        print("\nNo input provided (EOF). Exiting.")
        return
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return

    positions = []
    
    if choice == '1':
        print("Selected: Option 1 (Single Row)")
        positions = get_first_open_position()
    elif choice == '2':
        print("Selected: Option 2 (Full Analysis)")
        positions = get_all_open_positions()
    elif choice == '3':
        print("Selected: Option 3 (Negative Companies Analysis)")
        positions = get_negative_positions()
    else:
        print("Invalid choice. Exiting.")
        return

    if not positions:
        print("No positions found to process.")
        return

    print(f"Found {len(positions)} positions to process.")
    
    for row in positions:
        # row is (ticker, ticker_org, market)
        if len(row) == 3:
            ticker, ticker_org, market = row
            process_ticker(ticker, ticker_org, market)
        else:
            print(f"Skipping malformed row: {row}")

if __name__ == "__main__":
    main()
