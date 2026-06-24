import yfinance as yf
import requests
import pandas as pd
import re
import os.path
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.auth.exceptions

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = 'c'
df3 = pd.DataFrame()

def payload():
    payload = pd.read_html('https://www.biznesradar.pl/gielda/akcje_gpw')
    print(payload)
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
    print(tickers)
    us_market_list = pd.DataFrame()
    return tickers

def payloadUS():
    payload = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    print(payload)
    tickers = []
    two = payload[0]['Symbol'].tolist()
    for i in range(len(two)):
    #for i in range(10):
        pattern = '.'
#        if re.search(pattern, two[i]):
#            print(pattern)
#            print(two[i])
#            continue
        if two[i].count('.') == 1:
            continue
#        elif two[i] == 'A':
#            continue
        else:
            tickers.append(two[i])
    tickers.append('UNIT')
    tickers.append('RO.SW')
    return tickers



def us_market_list_def():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    records = []
    columns = []
    try:
        for tr in table.findAll("tr"):
            ths = tr.findAll("th")
            if ths != []:
                for each in ths:
                    columns.append(each.text)
            else:
                trs = tr.findAll("td")
                record = []
                for each in trs:
                    try:
                        link = each.find('a')['href']
                        text = each.text
                        record.append(text)
                        record.append(link)

                    except:
                        text = each.text
                        record.append(text)
                records.append(record)

        columns.insert(8, 'Link')
        columns.insert(9, 'Lsink')
        columns.insert(10, 'Lidnk')
        columns.insert(11, 'Lidnks')

        df = pd.DataFrame(data=records, columns = columns)
        df1= df.iloc[:, :2].copy()

        df1['Market'] = df1['Security'].str.extract(r'\.(.*?)\.')
        us_market_list = df1.drop('Security', axis=1)
    except ValueError as e:
        print(e)
        pass    
    
    us_market_list.columns.values[0] = 'Sym'
    us_market_list['Sym'] = us_market_list['Sym'].apply(lambda x: x.replace('\n', ''))
    column_names = us_market_list.columns.tolist()
    print(column_names)
    #column_names.to_excel('test_ticker1a.xlsx', sheet_name='sheet1', index=False)
    #us_market_list.to_excel('test_ticker1.xlsx', sheet_name='sheet1', index=False)
    print(us_market_list)
    return us_market_list

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

def metrics(tickers, us_market_list, procedure_choice):
    df3 = pd.DataFrame()
    #for tic in range(10):
    for tic in range(len(tickers)):
        #print(tic)
        #print(tickers[tic])
        # df = yf.download(tickers[tic],period='3mo', interval='1d')["Close"]      
        try:
            df = yf.Ticker(tickers[tic]).history(period='3mo')[['Close']]
            print("ml")
            print(us_market_list)
            print(tickers[tic])
            head2, sep2, tail2 = tickers[tic].partition('.')
            if tickers[tic] in us_market_list['Sym'].values:
                l4 = us_market_list.loc[us_market_list['Sym']==tickers[tic], 'Market'].values[0] 
                l1 = "https://www.tradingview.com/chart/?symbol="
                l3 = ":"
                link = l1 + l4 + l3 + tickers[tic]
                tickernon = tickers[tic]       
            elif tail2 == "WA": 
                tickernon = head2
                l1 = "https://www.tradingview.com/chart/?symbol=GPW:"
                link = l1 + head2
            else:
                tickernon = tickers[tic]
                link = "https://www.tradingview.com/chart/?symbol=:"
            k = df['Close'].ewm(span=12, adjust=False, min_periods=12).mean()
            d = df['Close'].ewm(span=26, adjust=False, min_periods=26).mean()
            macd = k - d
            macd_s = macd.ewm(span=9, adjust=False, min_periods=9).mean()
            macd_h = macd - macd_s
            df['macd'] = df.index.map(macd)  # driver
            df['macd_h'] = df.index.map(macd_h)  # divergence
            df['macd_s'] = df.index.map(macd_s)  # support
            df['ema32'] = df['Close'].ewm(span=32, adjust=False).mean()  # price
            LTH10 = df['Close'].tail(10).max()  # ATH limited to 10 sessions
            LTH30 = df['Close'].tail(30).max()  # ATH limited to 30 sessions
            try:
                close = float(df['Close'].values[-1:])
                macd_h14 = ((float(df['macd_h'].values[-1:]) + float(df['macd_h'].values[-2:-1]) + float(
                    df['macd_h'].values[-3:-2]) + float(df['macd_h'].values[-4:-3]) + float(
                    df['macd_h'].values[-5:-4]) + float(
                    df['macd_h'].values[-6:-5]) + float(df['macd_h'].values[-7:-6]) + float(
                    df['macd_h'].values[-8:-7]) + float(
                    df['macd_h'].values[-9:-8]) + float(df['macd_h'].values[-10:-9]) + float(
                    df['macd_h'].values[-11:-10]) + float(
                    df['macd_h'].values[-12:-11]) + float(df['macd_h'].values[-13:-12]) + float(
                    df['macd_h'].values[-14:-13])) / 14)
                macd_h10 = ((float(df['macd_h'].values[-1:]) + float(df['macd_h'].values[-2:-1]) + float(
                    df['macd_h'].values[-3:-2]) + float(df['macd_h'].values[-4:-3]) + float(
                    df['macd_h'].values[-5:-4]) + float(
                    df['macd_h'].values[-6:-5]) + float(df['macd_h'].values[-7:-6]) + float(
                    df['macd_h'].values[-8:-7]) + float(
                    df['macd_h'].values[-9:-8]) + float(df['macd_h'].values[-10:-9])) / 10)
                macd_h5 = ((float(df['macd_h'].values[-1:]) + float(df['macd_h'].values[-2:-1]) + float(
                    df['macd_h'].values[-3:-2]) + float(df['macd_h'].values[-4:-3]) + float(
                    df['macd_h'].values[-5:-4])) / 5)
                macd_14 = ((float(df['macd'].values[-1:]) + float(df['macd'].values[-2:-1]) + float(
                    df['macd'].values[-3:-2]) + float(df['macd'].values[-4:-3]) + float(df['macd'].values[-5:-4]) + float(
                    df['macd'].values[-6:-5]) + float(df['macd'].values[-7:-6]) + float(df['macd'].values[-8:-7]) + float(
                    df['macd'].values[-9:-8]) + float(df['macd'].values[-10:-9]) + float(
                    df['macd'].values[-11:-10]) + float(
                    df['macd'].values[-12:-11]) + float(df['macd'].values[-13:-12]) + float(
                    df['macd'].values[-14:-13])) / 14)
                macd_s14 = ((float(df['macd_s'].values[-1:]) + float(df['macd_s'].values[-2:-1]) + float(
                    df['macd_s'].values[-3:-2]) + float(df['macd_s'].values[-4:-3]) + float(
                    df['macd_s'].values[-5:-4]) + float(
                    df['macd_s'].values[-6:-5]) + float(df['macd_s'].values[-7:-6]) + float(
                    df['macd_s'].values[-8:-7]) + float(
                    df['macd_s'].values[-9:-8]) + float(df['macd_s'].values[-10:-9]) + float(
                    df['macd_s'].values[-11:-10]) + float(
                    df['macd_s'].values[-12:-11]) + float(df['macd_s'].values[-13:-12]) + float(
                    df['macd_s'].values[-14:-13])) / 14)
                ema32ok = ((((float(df['Close'].values[-1:]) + float(df['Close'].values[-2:-1]) + float(
                    df['Close'].values[-3:-2]) + float(df['Close'].values[-4:-3]) + float(df['Close'].values[-5:-4])) / 5)*100)/
                    ((float(df['ema32'].values[-1:]) + float(df['ema32'].values[-2:-1]) + float(df['ema32'].values[-3:-2])
                    +float(df['ema32'].values[-4:-3]) + float(df['ema32'].values[-5:-4])) / 5))-100
                price_change_3sessions = float(((df['Close'].values[-1:] * 100) / df['Close'].values[-3:-2]) - 100)
                price_change_5sessions = float(((df['Close'].values[-1:] * 100) / df['Close'].values[-5:-4]) - 100)
                price_change_10sessions = float(((df['Close'].values[-1:] * 100) / df['Close'].values[-10:-9]) - 100)
                price_change_15sessions = float(((df['Close'].values[-1:] * 100) / df['Close'].values[-15:-14]) - 100)
                price_change_30sessions = float(((df['Close'].values[-1:] * 100) / df['Close'].values[-30:-29]) - 100)
                price_change_58sessions = float(((df['Close'].values[-1:] * 100) / df['Close'].values[-58:-57]) - 100)

            except TypeError as e:
                print(e)
#                    macd_h14 = 0
#                    macd_h10 = 0
#                    macd_h5 = 0
#                    macd_14 = 0
#                    macd_s14 = 0
#                    ema32ok = 0
#                    close = 0
            try:
                ema_x = -10
                ema_score10 = 0


                if float(df['Close'].values[-1:]) > float(df['ema32'].values[-1:]):
                    ema_score10 = ema_score10 + 1
                else:
                    print("")
                while ema_x < 0:
                    if float(df['Close'].values[ema_x:ema_x + 1]) > float(df['ema32'].values[ema_x:ema_x + 1]):
                        ema_score10 = ema_score10 + 1
                    ema_x = ema_x + 1

            except TypeError as e:
                print("")
            try:
                ema_past1 = 0
                ema_xl = -2
                while ema_past1 == 0:
                    if float(df['Close'].values[ema_xl:ema_xl + 1]) < float(df['ema32'].values[ema_xl:ema_xl + 1]):
                        ema_past1 = ema_xl
                    ema_xl = ema_xl - 1

            except TypeError as e:
                print("")

            new_row = pd.DataFrame([[tickernon, tickers[tic], macd_14, macd_s14, ema32ok, LTH10, LTH30, macd_h14, macd_h10, macd_h5, link,
                                        price_change_3sessions, price_change_5sessions, price_change_10sessions,
                                        price_change_15sessions, price_change_30sessions, price_change_58sessions, close, ema_score10, ema_past1
                                        ]],
                                    columns=['tic', 'ticker', 'macd_14', 'macd_s14', 'ema32', 'LTH10', 'LTH30', 'macd_h14', 'macd_h10',
                                            'macd_h5',
                                            'link', 'price_change_3sessions', 'price_change_5sessions',
                                            'price_change_10sessions',
                                            'price_change_15sessions', 'price_change_30sessions', 'price_change_58sessions', 'Close', 'ema_score10', 'ema_past1'
                                            ])
            print(new_row)
            df3 = pd.concat([df3, new_row], ignore_index=True)
#            else:
 #               print("issue level 2")
  #              continue
        #except (KeyError, requests.exceptions.HTTPError, Exception) as e1:
        except (requests.exceptions.HTTPError) as e1:
            #print('issue')
            print(e1)
            print("master error")
            continue

    print(df3)
    df3 = df3.fillna(0)
    if procedure_choice == "1":
        df3.to_excel('list.xlsx', sheet_name='sheet1', index=False)
    elif procedure_choice == "2":
        df3.to_excel('listUS.xlsx', sheet_name='sheet1', index=False)
    elif procedure_choice == "4":
        df3.to_excel('listPROD.xlsx', sheet_name='sheet1', index=False) 
    else:
        print("Internal error")
    return df3

def metrics_fast(tickers):
    df4 = pd.DataFrame()

    snp_proces = yf.download(tickers, period="1d")['Close']
    print(snp_proces)
    snp_proces1 = snp_proces.transpose()
    snp_proces1 = snp_proces1.reset_index()
    print(snp_proces1)
    print(snp_proces1.columns)
    placeholder_col = [None] * len(snp_proces1)
    snp_proces1.insert(0, 'Placeholder2', placeholder_col)
    snp_proces1['CopiedColumn'] = snp_proces1['index']
#    snp_proces1.insert(1, 'Placeholder3', placeholder_col)
    snp_proces1.insert(2, 'Placeholder4', placeholder_col)
    snp_proces1.insert(3, 'Placeholder5', placeholder_col)
    snp_proces1.insert(4, 'Placeholder6', placeholder_col)
    snp_proces1.insert(5, 'Placeholder7', placeholder_col)
    snp_proces1.insert(6, 'Placeholder8', placeholder_col)
    snp_proces1.insert(7, 'Placeholder9', placeholder_col)
    snp_proces1.insert(8, 'Placeholder10', placeholder_col)
    snp_proces1.insert(9, 'Placeholder11', placeholder_col)
    snp_proces1.insert(10, 'Placeholder12', placeholder_col)
    snp_proces1.insert(11, 'Placeholder13', placeholder_col)
    snp_proces1.insert(12, 'Placeholder14', placeholder_col)
    snp_proces1.insert(13, 'Placeholder15', placeholder_col)
    snp_proces1.insert(14, 'Placeholder16', placeholder_col)
    snp_proces1.insert(14, 'Placeholder17', placeholder_col)
    snp_proces1.insert(14, 'Placeholder18', placeholder_col)
 #   snp_proces1 = snp_proces1.applymap(lambda x: "0" if math.isnan(x) else x)
    snp_proces1 = snp_proces1.fillna("0")
    print(snp_proces1)
    return snp_proces1

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
                flow = InstalledAppFlow.from_client_secrets_file('secrets\credentials.json', SCOPES)
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

def gsheet_com(creds):
    try:
        service = build('sheets', 'v4', credentials=creds)
        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId='1q0-tqU-C6_z11GfoCX4Ex4-QNYJhKsHFsLEYXjte5Iw', range="IN_GPW").execute()
        values = result.get('values', [])
        if not values:
            print('No data found.')
            return
    except (HttpError, google.auth.exceptions.RefreshError) as err:
        if os.path.exists('/token.json'):
            os.remove('/token.json')
            gsheet_com()
        else:
            gsheet_com()

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


        #response_date = service.spreadsheets().values().update(
        #    spreadsheetId=SPREADSHEET_ID,
        #    valueInputOption='RAW',
        #    range=RANGE_NAME,
        #    body=dict(majorDimension='ROWS',values=data2.T.reset_index().T.values.tolist())
        #).execute()###

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