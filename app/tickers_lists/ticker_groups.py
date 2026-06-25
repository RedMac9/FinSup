#import yfinance as yf
import requests
import pandas as pd
import re
#import os.path
from bs4 import BeautifulSoup
#from google.auth.transport.requests import Request
#from google.oauth2.credentials import Credentials
#from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
#mport google.auth.exceptions


def payload():
    payload = pd.read_html('https://www.biznesradar.pl/gielda/akcje_gpw')
#    print(payload)
    tickers = []
    two = payload[0]['Profil'].tolist()
    # print(tickers)
    for i in range(len(two)):
    #for i in range(10):
        pattern = 'document.write'
        if two[i] == 'Profil' or two[i] == "if(gdfp_async){":
            continue
        elif re.search(pattern, two[i]):
            continue
        else:
            head, sep, tail = two[i].partition(' ')
            tickers.append(head + '.WA')
#    print(tickers)
    us_market_list = pd.DataFrame()
    return tickers


import requests
import pandas as pd
from bs4 import BeautifulSoup

def us_market_list_def():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {
        'User-Agent': 'FinRepBot/1.0 (+contact: email@example.com) Python requests',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
    }

    # 1) Fetch HTML with a descriptive UA (per Wikimedia policy) and validate
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()  # raise on 4xx/5xx
    html = resp.text

    # 2) Parse DOM
    soup = BeautifulSoup(html, 'lxml')

    # 3) Try strict: find the wikitable sortable whose header includes 'Symbol' and 'Security'
    def get_headers(tbl):
        tr = tbl.find('tr')
        if not tr:
            return []
        return [th.get_text(strip=True) for th in tr.find_all('th')]

    tables = soup.find_all('table', class_='wikitable sortable')
    target = None
    for tbl in tables:
        hdrs = get_headers(tbl)
        # normalize header tokens to lower for robust comparison
        hdrs_lower = [h.lower() for h in hdrs]
        if 'symbol' in hdrs_lower and ('security' in hdrs_lower or 'company' in hdrs_lower):
            target = tbl
            break

    # 4) If not found, try any wikitable that has a 'symbol' column at all
    if target is None:
        for tbl in soup.find_all('table', class_='wikitable'):
            hdrs = get_headers(tbl)
            hdrs_lower = [h.lower() for h in hdrs]
            if 'symbol' in hdrs_lower:
                target = tbl
                break

    rows = []
    if target is not None:
        # 5) Parse rows from the chosen table
        header_map = {h.lower(): i for i, h in enumerate(get_headers(target))}
        sym_idx = header_map.get('symbol', 0)  # default to first col if odd header
        sec_idx = header_map.get('security', header_map.get('company', 1))  # try 'company' fallback

        for tr in target.find_all('tr')[1:]:
            tds = tr.find_all('td')
            if not tds:
                continue
            # bounds checking
            if sym_idx >= len(tds):
                continue
            symbol = tds[sym_idx].get_text(strip=True).replace('\n', '')
            security = ''
            if sec_idx is not None and sec_idx < len(tds):
                security = tds[sec_idx].get_text(strip=True)
            if symbol:
                rows.append((symbol, security))

    # 6) Final fallback: use pandas.read_html on the fetched HTML if DOM selection yielded no rows
    if not rows:
        dfs = pd.read_html(html)  # pandas usually returns the components table first
        # find the frame that has 'Symbol' in columns (robust to order)
        table = next((df for df in dfs if any(str(c).strip().lower() == 'symbol' for c in df.columns)), None)
        if table is None and dfs:
            table = dfs
        if table is None or 'Symbol' not in table.columns:
            raise RuntimeError("S&P 500 components table not found via DOM or pandas parsing.")
        # Some mirrors localize headers; map case-insensitively
        def col_find(df, name):
            for c in df.columns:
                if str(c).strip().lower() == name:
                    return c
            return None
        sym_col = col_find(table, 'symbol')
        sec_col = col_find(table, 'security') or col_find(table, 'company') or table.columns[9]
        series_sym = table[sym_col].astype(str).str.replace('\n', '', regex=False).str.strip()
        series_sec = table[sec_col].astype(str).str.strip()
        rows = list(zip(series_sym.tolist(), series_sec.tolist()))

    # 7) Construct final DataFrame
    df = pd.DataFrame(rows, columns=['Sym', 'Security'])
    df['Market'] = 'US'
    # Optional: print previews
    print(df.columns.tolist())
    print(df.head())
    return df


def payloadPROD(creds):
    try:
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = '1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw'
        range_name = 'List_PROD!A:A'
        # Make the API request to retrieve the data
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        # Extract the values from the response
        values = result.get('values')
        print(values)
        # Print the imported data
        tickers = []
        if values:
            for row in values:
#                print(row)
                row = row[0]
                tickers.append(row)
        else:
            print('No data found.')
        print(f"Data written to 'spreadsheet successfully!")
    except HttpError as error:
        print(f"An error occurred: {error}")
    print(tickers)
    return tickers



def payload_push(creds):
    """
    Pobiera dane z Google Sheets i zwraca je jako lista list.
    Każda wewnętrzna lista to wiersz z arkusza.
    """
    try:
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = '1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw'
        range_name = 'List_PROD_graph!D:M'  # Pobierasz wiele kolumn

        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values')

        if not values:
            print('No data found.')
            return []  # Zwróć pustą listę, jeśli nie ma danych

        print("Dane z arkusza zostały pobrane pomyślnie!")
        # Zwracamy całą listę list, bez jej spłaszczania
        return values 

    except HttpError as error:
        print(f"An error occurred: {error}")
        return [] # Zwróć pustą listę w przypadku błędu



def default_filter_graph(creds):
    # Google Sheets functionality disabled as requested.
    # Returning an empty list to avoid service account key errors.
    return []

# def default_filter_graph_OLD(creds):
#     try:
#         service = build('sheets', 'v4', credentials=creds)
#         spreadsheet_id = '1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw'
#         range_name = 'List_PROD_graph!A:A'
#         # Make the API request to retrieve the data
#         result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
#         # Extract the values from the response
#         values = result.get('values')
#         print(values)
#         # Print the imported data
#         default_tickers = []
#         if values:
#             for row in values:
# #                print(row)
#                 row = row[0]
#                 default_tickers.append(row)
#         else:
#             print('No data found.')
#         print(f"Data written to 'spreadsheet successfully!")
#     except HttpError as error:
#         print(f"An error occurred: {error}")
#     print(default_tickers)
#     return default_tickers



import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables from secrets.env located in the app root (FinRep2)
secrets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'secrets.env'))
load_dotenv(secrets_path)

def payloadPROD_db():
    """
    Fetches a list of tickers from the v_open_positions view in the database.
    """
    tickers = []
    conn = None
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return []

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        print("Successfully connected to the database for fetching tickers.")

        with conn.cursor() as cur:
            query = sql.SQL("SELECT ticker FROM {schema}.v_open_positions;").format(schema=sql.Identifier(db_schema))
            cur.execute(query)
            rows = cur.fetchall()
            tickers = [row[0] for row in rows]
            print(f"Successfully fetched {len(tickers)} tickers from the database.")

    except psycopg2.Error as error:
        print(f"Database error while fetching tickers: {error}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

    return tickers


def payload_reit_db():
    """Return the set of open-position tickers flagged as REIT.

    Joins v_open_positions (transformed ticker form, matching the CSV/sidebar)
    with blacklisted_tickers where reason = 'REIT'.
    """
    reits = set()
    conn = None
    db_schema = os.environ.get("DB_SCHEMA")
    if not db_schema:
        print("Database error: DB_SCHEMA environment variable not set.")
        return reits

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
        )
        with conn.cursor() as cur:
            query = sql.SQL(
                "SELECT op.ticker FROM {schema}.v_open_positions op "
                "JOIN {schema}.blacklisted_tickers bt ON op.ticker_org = bt.ticker "
                "WHERE bt.reason = 'REIT';"
            ).format(schema=sql.Identifier(db_schema))
            cur.execute(query)
            reits = {row[0] for row in cur.fetchall()}
            print(f"Successfully fetched {len(reits)} REIT tickers from the database.")
    except psycopg2.Error as error:
        print(f"Database error while fetching REIT tickers: {error}")
    finally:
        if conn:
            conn.close()

    return reits

# Hardcoded ETF Ticker Lists

# US Market ETFs
US_MARKET_ETF_TICKERS = [
    "SPY",  # SPDR S&P 500 ETF Trust
    "IVV",  # iShares Core S&P 500 ETF
    "VTI",  # Vanguard Total Stock Market ETF
    "VOO",  # Vanguard S&P 500 ETF
    "QQQ",  # Invesco QQQ Trust (NASDAQ-100)
]

# Global Market ETFs (excluding US)
GLOBAL_MARKET_ETF_TICKERS = [
    "VEA",  # Vanguard FTSE Developed Markets ETF
    "IEFA", # iShares Core MSCI EAFE ETF
    "VEU",  # Vanguard FTSE All-World ex-US ETF
    "VXUS", # Vanguard Total International Stock ETF
]

# Emerging Markets ETFs
EMERGING_MARKETS_ETF_TICKERS = [
    "VWO",  # Vanguard FTSE Emerging Markets ETF
    "IEMG", # iShares Core MSCI Emerging Markets ETF
    "EEM",  # iShares MSCI Emerging Markets ETF
]

# Dividend ETFs
DIVIDEND_ETF_TICKERS = [
    "VIG",  # Vanguard Dividend Appreciation ETF
    "VYM",  # Vanguard High Dividend Yield ETF
    "SCHD", # Schwab U.S. Dividend Equity ETF
    "DGRO", # iShares Core Dividend Growth ETF
]

# Bond ETFs
BOND_ETF_TICKERS = [
    "AGG",  # iShares Core U.S. Aggregate Bond ETF
    "BND",  # Vanguard Total Bond Market ETF
    "LQD",  # iShares iBoxx $ Investment Grade Corporate Bond ETF
    "HYG",  # iShares iBoxx $ High Yield Corporate Bond ETF
]

# Polish Market ETFs (GPW)
POLISH_ETF_TICKERS = [
    "ETFW20L.WA",   # Lyxor ETF WIG20
    "ETFSP500.WA",  # Lyxor ETF S&P 500
    "ETFDAX.WA",    # Lyxor ETF DAX
]