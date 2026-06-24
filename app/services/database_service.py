import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables from secrets.env located in the app root (FinRep2)
secrets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'secrets.env'))
load_dotenv(secrets_path)

# Lazily-created SQLAlchemy engine, reused across read queries.
# pandas read_sql officially supports a SQLAlchemy connectable; using the
# engine here removes the "DBAPI2 objects are not tested" warning and adds
# connection pooling with pre-ping (helpful for the remote mikr.us DB).
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        url = URL.create(
            "postgresql+psycopg2",
            username=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
        )
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine

def save_metrics_to_db(metrics_df: pd.DataFrame):
    """
    Saves metrics from a DataFrame to the tickers_metrics table in the database.
    Performs an 'UPSERT' operation based on the (ticker, date) primary key.
    """
    conn = None
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return

    # Columns in the tickers_metrics table
    db_columns = [
        'ticker', 'date', 'close', 'pct_diff_ath10', 'pct_diff_ath30',
        'DaysCloseAboveSMA10_Last30_', 'DaysCloseAboveEMA10_Last30_',
        'DaysCloseAboveSMA20_Last30_', 'DaysCloseAboveEMA20_Last30_',
        'DaysCloseAboveEMA32_Last30_', 'DaysCloseAboveSMA50_Last30_',
        'DaysCloseAboveEMA50_Last30_', 'DaysCloseAboveSMA100_Last30_',
        'DaysCloseAboveEMA100_Last30_', 'DaysCloseAboveDMA25x5_Last30_',
        'market', 'market_real', 'tradingview_url', 'pct_change_last'
    ]

    # Filter the DataFrame to only include columns that exist in the database table
    df_to_insert = metrics_df[[col for col in db_columns if col in metrics_df.columns]].copy()

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        print("Successfully connected to the database.")

        with conn.cursor() as cur:
            
            # Prepare the column names for the SQL query
            cols = df_to_insert.columns.tolist()
            cols_sql = sql.SQL(', ').join(map(sql.Identifier, cols))
            
            # Prepare the SET part for the ON CONFLICT clause
            update_cols_sql = sql.SQL(', ').join([
                sql.SQL('{0} = EXCLUDED.{0}').format(sql.Identifier(col)) for col in cols if col not in ['ticker', 'date']
            ])

            # Prepare the full query
            query = sql.SQL("""
                INSERT INTO {schema}.tickers_metrics ({cols})
                VALUES ({placeholders})
                ON CONFLICT (ticker, date) DO UPDATE SET {update_cols};
            """).format(
                schema=sql.Identifier(db_schema),
                cols=cols_sql,
                placeholders=sql.SQL(', ').join(sql.Placeholder() * len(cols)),
                update_cols=update_cols_sql
            )

            # Execute the query for each row in the DataFrame
            for row in df_to_insert.itertuples(index=False, name=None):
                cur.execute(query, row)
            
            conn.commit()
            print(f"Successfully upserted {len(df_to_insert)} rows into tickers_metrics.")

    except psycopg2.Error as error:
        print(f"Database error: {error}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

def get_open_positions_metrics():
    """
    Fetches data from the v_open_positions_metrics view and returns it as a DataFrame.
    """
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return pd.DataFrame() # Return empty DataFrame

    try:
        engine = _get_engine()
        qschema = engine.dialect.identifier_preparer.quote(db_schema)
        df = pd.read_sql_query(
            text(f"SELECT * FROM {qschema}.v_open_positions_metrics"), engine
        )
        print(f"Successfully fetched {len(df)} rows from v_open_positions_metrics.")

        # Convert 'date' column to string to avoid JSON serialization errors
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)

        return df

    except SQLAlchemyError as error:
        print(f"Database error: {error}")
        return pd.DataFrame() # Return empty DataFrame on error

def get_trade_txns():
    """
    Fetches data from the trade_txn table and returns it as a DataFrame.
    """
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return pd.DataFrame()

    try:
        engine = _get_engine()
        qschema = engine.dialect.identifier_preparer.quote(db_schema)
        df = pd.read_sql_query(
            text(f"SELECT * FROM {qschema}.trade_txn ORDER BY exec_time_utc DESC"),
            engine,
        )
        print(f"Successfully fetched {len(df)} rows from trade_txn.")

        return df

    except SQLAlchemyError as error:
        print(f"Database error: {error}")
        return pd.DataFrame()

def update_trade_txn(txn_id, updated_data):
    """
    Updates a single trade transaction in the database.
    """
    conn = None
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return False

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        
        # Filter updated_data to only include valid columns (excluding txn_id)
        valid_cols = [
            'ticker', 'market', 'side', 'exec_time_utc', 'currency', 'broker',
            'portfolio', 'quantity', 'price', 'gross_amount', 'fee', 'tax',
            'other_cost', 'broker_txn_id', 'note'
        ]
        data_to_update = {}
        for k, v in updated_data.items():
            if k in valid_cols:
                # Handle empty strings as None (NULL in DB)
                if v == "" or (isinstance(v, float) and pd.isna(v)):
                    data_to_update[k] = None
                else:
                    data_to_update[k] = v

        if not data_to_update:
            return False

        with conn.cursor() as cur:
            set_parts = []
            values = []
            for col, val in data_to_update.items():
                set_parts.append(sql.SQL("{0} = %s").format(sql.Identifier(col)))
                values.append(val)
            
            values.append(txn_id)
            
            query = sql.SQL("UPDATE {schema}.trade_txn SET {set_clause} WHERE txn_id = %s").format(
                schema=sql.Identifier(db_schema),
                set_clause=sql.SQL(', ').join(set_parts)
            )

            cur.execute(query, values)
            conn.commit()
            print(f"Successfully updated txn_id {txn_id}.")
            return True

    except psycopg2.Error as error:
        print(f"Database error: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def insert_trade_txn(data):
    """
    Inserts a new trade transaction into the database.
    """
    conn = None
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return False

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        
        valid_cols = [
            'ticker', 'market', 'side', 'exec_time_utc', 'currency', 'broker',
            'portfolio', 'quantity', 'price', 'gross_amount', 'fee', 'tax',
            'other_cost', 'broker_txn_id', 'note'
        ]
        
        data_to_insert = {}
        for col in valid_cols:
            val = data.get(col)
            if val == "" or (isinstance(val, float) and pd.isna(val)):
                data_to_insert[col] = None
            else:
                data_to_insert[col] = val

        if not data_to_insert:
            return False

        with conn.cursor() as cur:
            cols = list(data_to_insert.keys())
            vals = list(data_to_insert.values())
            
            query = sql.SQL("INSERT INTO {schema}.trade_txn ({cols}) VALUES ({placeholders})").format(
                schema=sql.Identifier(db_schema),
                cols=sql.SQL(', ').join(map(sql.Identifier, cols)),
                placeholders=sql.SQL(', ').join(sql.Placeholder() * len(cols))
            )

            cur.execute(query, vals)
            conn.commit()
            print("Successfully inserted new transaction.")
            return True

    except psycopg2.Error as error:
        print(f"Database error: {error}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_roi_summary():
    """
    Fetches data from the v_roi_summary view and returns it as a DataFrame.
    """
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return pd.DataFrame() # Return empty DataFrame

    try:
        engine = _get_engine()
        qschema = engine.dialect.identifier_preparer.quote(db_schema)
        df = pd.read_sql_query(
            text(f"SELECT * FROM {qschema}.v_roi_summary"), engine
        )
        print(f"Successfully fetched {len(df)} rows from v_roi_summary.")

        # Convert 'date' column to string to avoid JSON serialization errors
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)

        return df

    except SQLAlchemyError as error:
        print(f"Database error: {error}")
        return pd.DataFrame() # Return empty DataFrame on error