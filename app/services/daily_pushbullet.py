from pushbullet import Pushbullet
import pandas as pd
from datetime import datetime
import os
import json
from services.database_service import get_open_positions_metrics

def load_api_key(filepath: str) -> str | None:
    """
    Loads the API key from a JSON file.
    Assumes the file structure is: {"api_key": "your_key"}
    """
    try:
        with open(filepath, 'r') as f:
            secrets = json.load(f)
            return secrets.get('api_key')
    except FileNotFoundError:
        print(f"Error: API key file not found at path: {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in file: {filepath}")
        return None

def send_push_notification():
    """
    Fetches data from the v_open_positions_metrics view, filters it,
    sorts the results, and sends a formatted Pushbullet notification.
    """
    api_key_path = os.path.join('secrets', 'pushbullet.json')
    API_KEY = load_api_key(api_key_path)
    
    if not API_KEY:
        print("Failed to load API key. Notification sending aborted.")
        return

    # STEP 1: FETCH DATA FROM DATABASE
    data_df = get_open_positions_metrics()

    if data_df.empty:
        print("Received empty DataFrame from database (v_open_positions_metrics). Notification will not be sent.")
        return

    # STEP 2: PREPARE AND FILTER DATA
    # Ensure columns are numeric
    data_df['pct_change_last'] = pd.to_numeric(data_df['pct_change_last'], errors='coerce')
    data_df['pct_diff_ath30'] = pd.to_numeric(data_df['pct_diff_ath30'], errors='coerce')
    data_df['pct_diff_from_avg_buy'] = pd.to_numeric(data_df['pct_diff_from_avg_buy'], errors='coerce')

    # Filter: pct_change_last <= 0
    final_df = data_df[data_df['pct_change_last'] <= 0].copy()

    if final_df.empty:
        print("No companies meet the criteria (pct_change_last <= 0). Notification will not be sent.")
        return

    # STEP 3: SORTING
    # Logic:
    # 1. Non-REIT tickers first, REIT tickers last.
    # 2. Within those groups, sort by pct_change_last in descending order.
    
    if 'category' in final_df.columns:
        # Create a helper column for sorting: 0 for non-REIT, 1 for REIT
        final_df['is_reit'] = final_df['category'].apply(lambda x: 1 if x == 'REIT' else 0)
        
        final_df.sort_values(
            by=['is_reit', 'pct_change_last'],
            ascending=[True, True], # False for descending order
            inplace=True
        )
    else:
        # If category is missing, just sort by pct_change_last descending
        final_df.sort_values(by=['pct_change_last'], ascending=True, inplace=True)

    try:
        pb = Pushbullet(API_KEY)
    except Exception as e:
        print(f"Pushbullet initialization error: {e}")
        return

    # STEP 4: PREPARE AND SEND NOTIFICATION
    # Map column names to output format
    column_mapping = {
        'category': 'Group',
        'pct_diff_from_avg_buy': 'diff_from_buy_%',
        'DaysCloseAboveEMA32_Last30_': 'DaysAboveEMA32',
    }
    final_df.rename(columns=column_mapping, inplace=True)

    # Define columns to include in the message, with 'Group' at the end
    columns_to_pass = [
        'ticker',
        'pct_diff_ath30',
        'pct_change_last',
        'diff_from_buy_%',
        'DaysAboveEMA32',
        'Group'
    ]
    
    # Select available columns
    available_cols = [c for c in columns_to_pass if c in final_df.columns]
    filtered_df = final_df[available_cols]
    
    report_date = datetime.now().strftime('%Y-%m-%d')
    title = f"Stock Analysis Report {report_date}"

    message_blocks = []
    for _, row in filtered_df.iterrows():
        row_details = []
        for col_name, value in row.items():
            if isinstance(value, (int, float)):
                value = round(value, 2)
            row_details.append(f"{col_name}: {value}")
        message_blocks.append('\n'.join(row_details))

    message_body = '\n\n'.join(message_blocks)

    print("Sending Pushbullet notification...")
    pb.push_note(title, message_body)
    print("Notification sent successfully!")
    
    print("\nGenerated message body:")
    print(message_body)
