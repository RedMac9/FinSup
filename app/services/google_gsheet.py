import pandas as pd
import numpy as np
import os # Imported to handle file paths robustly
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw'


def _values_for_sheets(df):
    """
    Converts a DataFrame to a list-of-lists safe for the Sheets API.
    NaN/inf are not valid JSON tokens and make the API reject the whole
    payload with a 400 "Invalid JSON payload" error, so they're replaced
    with None (serializes to JSON null) before the values are collected.
    """
    clean = df.replace([np.inf, -np.inf], np.nan).astype(object)
    clean = clean.where(pd.notnull(clean), None)
    return [df.columns.tolist()] + clean.values.tolist()

# Anchored to this file's location (not the process cwd), so auth doesn't
# silently fail when the app is launched from a different working directory.
SERVICE_ACCOUNT_FILE = os.path.join(
    os.path.dirname(__file__), '..', '..', 'secrets', 'finsup2-proj-90ea4909d4c5.json'
)


def init_client():
    """
    Initializes and authenticates a client using a service account key file.
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    except FileNotFoundError:
        print(f"Error: The service account key file was not found at '{SERVICE_ACCOUNT_FILE}'.")
        print("Please ensure the 'secrets' folder exists and the JSON key file is inside it.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during authentication: {e}")
        return None
    return creds


def gsheet_com(creds):
    """
    Reads data from a specified range in a Google Sheet.
    """
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="IN_GPW").execute()
        values = result.get('values', [])
        
        if not values:
            print('No data found.')
            return None
        return values
        
    except HttpError as err:
        print(f"An HTTP error occurred: {err}")
        return None


def gsheet_update(metrics1, creds, procedure_choice):
    """
    Clears a sheet and writes a pandas DataFrame to it.
    """
    if not isinstance(metrics1, pd.DataFrame):
        print("Error: Input data is not a pandas DataFrame.")
        return
    if metrics1.empty:
        print("Warning: The DataFrame is empty. Nothing to write.")
        return

    print("Input DataFrame (metrics1) sample:")
    print(metrics1.head())

    if creds is None:
        print("Error: No credentials available (init_client() failed earlier). Skipping Google Sheets update.")
        return

    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet_name = ""
        if procedure_choice == "1":
            sheet_name = "IN_GPW"
        elif procedure_choice == "2":
            sheet_name = "IN_S&P500"
        elif procedure_choice == "3":
            sheet_name = "IN_US"
        elif procedure_choice == "4":
            sheet_name = "IN_PROD2"
        else:
            print("Internal error: Invalid procedure_choice.")
            return

        range_to_write = f"{sheet_name}!A1"
        range_to_clear = sheet_name

        sheet = service.spreadsheets()

        print(f"\nClearing sheet: '{range_to_clear}'")
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_clear,
            body={}
        ).execute()

        values_to_write = _values_for_sheets(metrics1)

        print(f"Writing {len(values_to_write)} rows to '{range_to_write}'...")
        
        update_body = {'values': values_to_write}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_write,
            valueInputOption='RAW',
            body=update_body
        ).execute()

        print(f"Data written to '{sheet_name}' successfully!")

    except HttpError as error:
        print(f"An HttpError occurred: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def gsheet_update_db(metrics1, creds):
    """
    Clears a sheet and writes a pandas DataFrame to it.
    """
    if not isinstance(metrics1, pd.DataFrame):
        print("Error: Input data is not a pandas DataFrame.")
        return
    if metrics1.empty:
        print("Warning: The DataFrame is empty. Nothing to write.")
        return

    print("Input DataFrame (metrics1) sample:")
    print(metrics1.head())

    if creds is None:
        print("Error: No credentials available (init_client() failed earlier). Skipping Google Sheets update.")
        return

    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet_name = "ON"

        range_to_write = f"{sheet_name}!A1"
        range_to_clear = sheet_name

        sheet = service.spreadsheets()

        print(f"\nClearing sheet: '{range_to_clear}'")
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_clear,
            body={}
        ).execute()

        values_to_write = _values_for_sheets(metrics1)

        print(f"Writing {len(values_to_write)} rows to '{range_to_write}'...")
        
        update_body = {'values': values_to_write}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_write,
            valueInputOption='RAW',
            body=update_body
        ).execute()

        print(f"Data written to '{sheet_name}' successfully!")

    except HttpError as error:
        print(f"An HttpError occurred: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def gsheet_update_db_roi(metrics1, creds):
    """
    Clears a sheet and writes a pandas DataFrame to it.
    """
    if not isinstance(metrics1, pd.DataFrame):
        print("Error: Input data is not a pandas DataFrame.")
        return
    if metrics1.empty:
        print("Warning: The DataFrame is empty. Nothing to write.")
        return

    print("Input DataFrame (metrics1) sample:")
    print(metrics1.head())

    if creds is None:
        print("Error: No credentials available (init_client() failed earlier). Skipping Google Sheets update.")
        return

    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet_name = "ON_ROI"

        range_to_write = f"{sheet_name}!A1"
        range_to_clear = sheet_name

        sheet = service.spreadsheets()

        print(f"\nClearing sheet: '{range_to_clear}'")
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_clear,
            body={}
        ).execute()

        values_to_write = _values_for_sheets(metrics1)

        print(f"Writing {len(values_to_write)} rows to '{range_to_write}'...")
        
        update_body = {'values': values_to_write}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_write,
            valueInputOption='RAW',
            body=update_body
        ).execute()

        print(f"Data written to '{sheet_name}' successfully!")

    except HttpError as error:
        print(f"An HttpError occurred: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Example Usage ---
if __name__ == '__main__':
    # 1. Authenticate and get credentials
    credentials = init_client()

    if credentials:
        print("Authentication successful.")
        
        # 2. Example: Create a sample DataFrame to upload
        sample_data = {
            'Ticker': ['CDPROJEKT', 'PKO BP', 'ALIOR'],
            'Price': [120.50, 55.30, 98.75],
            'Volume': [1500000, 2300000, 850000]
        }
        df_to_upload = pd.DataFrame(sample_data)

        # 3. Choose a procedure (e.g., "1" for "IN_GPW" sheet) and update the sheet
        procedure = "1"
        gsheet_update(df_to_upload, credentials, procedure)
        
    else:
        print("Authentication failed. Cannot proceed.")