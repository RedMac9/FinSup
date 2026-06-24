from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.auth.exceptions

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = 'c'
df3 = pd.DataFrame()


def init_client():
    try:
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
    except (HttpError, google.auth.exceptions.RefreshError) as err:
        if os.path.exists('token.json'):
            os.remove('token.json')
            init_client()
        else:
            init_client()
    return(creds)

def gsheet_update_GPW(metrics1, creds, procedure_choice):
    print(metrics1)
    try:
        service = build('sheets', 'v4', credentials=creds)
        if procedure_choice == "1":
            range_set="IN_GPW"
        elif procedure_choice == "2":
            range_set="IN_S&P500"
        elif procedure_choice == "4":
            range_set="IN_PROD"
        else:
            print("Internal error")
        sheet = service.spreadsheets()
        print(metrics1)
        clear_body = {'range': range_set}
        sheet.values().clear(spreadsheetId='1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw', range=range_set, body=clear_body).execute()
        update_body = {'values': metrics1.values.tolist()}
        sheet.values().update(spreadsheetId='1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw', range=range_set, valueInputOption='RAW',
                             body=update_body).execute()


   
        print(f"Data written to 'spreadsheet successfully!")
    except HttpError as error:
        print(f"An error occurred: {error}")

def main():
    while True:
        print("Which market would you like to trigger?")
        print("1. GPW")
        print("2. S&P500")
        print("3. GPW + S&P500")
        print("4. fast PROD")
        procedure_choice = input("Enter the procedure number: ")
        creds = init_client()
        if procedure_choice == "1":
            tickers = payload()
            metrics1 = metrics(tickers, procedure_choice)
            creds = init_client()
            gsheet_update_GPW(metrics1, creds, procedure_choice)
            break
        elif procedure_choice == "2":
            tickers = payloadUS()
            us_market_list = us_market_list_def()
            #print(tickers)
            metrics1 = metrics(tickers, us_market_list, procedure_choice)
            creds = init_client()
            gsheet_update_GPW(metrics1, creds, procedure_choice)
            break
        elif procedure_choice == "3":
            tickers = payload()
            us_market_list = us_market_list_def()
            metrics1 = metrics(tickers, us_market_list, procedure_choice='1')
            gsheet_update_GPW(metrics1, creds,  procedure_choice='1')
            tickers = payloadUS()
            metrics1 = metrics(tickers, us_market_list,  procedure_choice='2')
            creds = init_client()
            gsheet_update_GPW(metrics1, creds,  procedure_choice='2')
            break
        elif procedure_choice == "4":
            creds = init_client()
            tickers = payloadPROD(creds)
            us_market_list = us_market_list_def()
            metrics1 = metrics(tickers, us_market_list, procedure_choice)
            gsheet_update_GPW(metrics1, creds,  procedure_choice)
            break
        else:
            print("Invalid choice. Please enter 1,2,3 or 4")
    print(tickers)

if __name__ == '__main__':
    main()