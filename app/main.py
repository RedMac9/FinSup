import sys
from services.google_gsheet import init_client, gsheet_update, gsheet_update_db, gsheet_update_db_roi
from tickers_lists.ticker_groups import payload, payloadPROD, default_filter_graph, us_market_list_def, payload_push, payloadPROD_db, us_other_list_def, US_MIN_DOLLAR_VOLUME
from tickers_lists.etf_list import etf_list
from services.market_metrics import metrics_separate_tabs, seed_exchange_cache
from services.market_config  import market_mappings 
from output.graph import graph_start
from output.trade_txn_editor import trade_txn_editor_start
from output.positions_chart import positions_chart_start
from services.daily_pushbullet  import send_push_notification 
from services.exchange_rate import run_exchange_rate_update
from services.database_service import save_metrics_to_db, get_open_positions_metrics, get_roi_summary



def run_procedure(procedure_choice):
    if procedure_choice == "1":
        creds = init_client()
        tickers = payload()
        metrics1 = metrics_separate_tabs(tickers, procedure_choice, market_mappings)
        gsheet_update(metrics1, creds, procedure_choice)
    elif procedure_choice == "2":
        creds = init_client()
        sp500_df = us_market_list_def()
        tickers = [
            symbol for symbol in sp500_df['Sym'].tolist() if str(symbol).count('.') != 1
        ]
        metrics1 = metrics_separate_tabs(tickers, procedure_choice, market_mappings)
        gsheet_update(metrics1, creds, procedure_choice)
    elif procedure_choice == "3":
        creds = init_client()
        us_df = us_other_list_def()
        seed_exchange_cache(dict(zip(us_df['Sym'], us_df['Exchange'])))
        tickers = us_df['Sym'].tolist()
        metrics1 = metrics_separate_tabs(tickers, procedure_choice, market_mappings,
                                         min_dollar_volume=US_MIN_DOLLAR_VOLUME)
        gsheet_update(metrics1, creds, procedure_choice)
    elif procedure_choice == "4":
        run_exchange_rate_update()
        creds = init_client()
        tickers = payloadPROD_db()
        metrics1 = metrics_separate_tabs(tickers, procedure_choice, market_mappings)
        save_metrics_to_db(metrics1)
        open_positions_metrics = get_open_positions_metrics()
        gsheet_update_db(open_positions_metrics, creds)
        roi_summary = get_roi_summary()
        gsheet_update_db_roi(roi_summary, creds)               
        gsheet_update(metrics1, creds,  procedure_choice)
        tickers_push = payload_push(creds)
        send_push_notification()
    elif procedure_choice == "5":
        def_filter_graph_list = default_filter_graph(None)  
        graph = graph_start(procedure_choice, def_filter_graph_list)
    elif procedure_choice == "6":
        def_filter_graph_list = default_filter_graph(None)  
        graph = graph_start(procedure_choice, def_filter_graph_list)
    elif procedure_choice == "7":
        def_filter_graph_list = default_filter_graph(None)            
        graph = graph_start(procedure_choice, def_filter_graph_list)
    elif procedure_choice == "10":
        def_filter_graph_list = default_filter_graph(None)
        graph = graph_start(procedure_choice, def_filter_graph_list)
    elif procedure_choice == "8":
        print("pass")
    elif procedure_choice == "9":
        send_push_notification()
    elif procedure_choice == "12":
        creds = init_client()
        tickers = etf_list
        metrics1 = metrics_separate_tabs(tickers, procedure_choice, market_mappings)
        gsheet_update(metrics1, creds,  procedure_choice)
    elif procedure_choice == "13":
        def_filter_graph_list = default_filter_graph(None)
        graph = graph_start(procedure_choice, def_filter_graph_list)
    elif procedure_choice == "14":
        run_exchange_rate_update()
        creds = init_client()
        tickers = payloadPROD_db()
        metrics1 = metrics_separate_tabs(tickers, procedure_choice, market_mappings)
        save_metrics_to_db(metrics1)
        open_positions_metrics = get_open_positions_metrics()
        gsheet_update_db(open_positions_metrics, creds)
        roi_summary = get_roi_summary()
        gsheet_update_db_roi(roi_summary, creds)
    elif procedure_choice == "15":
        trade_txn_editor_start()
    elif procedure_choice == "16":
        positions_chart_start()
    else:
        print("Invalid choice.")

def main():
    procedure_choice = None
    if len(sys.argv) > 1:
        procedure_choice = sys.argv[1]
    else:
        print("Which market would you like to trigger?")
        print("1. GPW")
        print("2. S&P500")
        print("3. US (NYSE + NASDAQ, ex S&P500)")
        print("4. fast PROD")
        print("5. graph GPW")
        print("6. graph S&P 500")
        print("7. graph PROD")
        print("9. push notification test")
        print("10. graph US")
        print("12. ETF")
        print("13. graph ETF")
        print("14. exchange rates")
        print("15. trade txn editor")
        print("16. open positions chart")
        procedure_choice = input("Enter the procedure number: ")

    run_procedure(procedure_choice)

#    print(tickers)
               

if __name__ == "__main__":
    main()