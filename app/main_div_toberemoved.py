from dividends.data_fetch import get_nasdaq_tickers, fetch_dividend_data_last_year, get_current_price, get_dividend_frequency, get_capitalization_volume
from dividends.calculations import calculate_theoretical_return
from dividends.data_transformation import display_results, results_to_excel
from dividends.visualization import combine_df

import pandas as pd
import openpyxl
import sys

sys.setrecursionlimit(10000)

formatted_results = []

def main():
#    tickers = ["AAPL", "O", "MSFT", "VNQ","ALB","AXON","AMD","AKAM","AMZN","AON"]  # Example tickers
#    tickers = ["ALB","AMZN"]
    tickers = ["ACRE","BXMT","CHMI","DOC","DSX","DX","FAT","FMC","IVR","PFE","TRTX","TWNP","TWO"] #my ticers
#    tickers = get_sp500_tickers()
#    tickers = get_nasdaq_tickers()
#   
    investment = 1000  # Fixed investment amount

    for ticker in tickers:
        print(f"Processing {ticker}...")
        
        try:
            # Fetch dividend data for the last year and calculate median dividend
            dividends, median_dividend = fetch_dividend_data_last_year(ticker)
            #print(dividends)
            #print(median_dividend)

            # Fetch current stock price
            current_price = get_current_price(ticker)
            #print(current_price)

            # Fetch current stock price
            market_cap, avg_volume, sector, industry = get_capitalization_volume(ticker)
            #print(market_cap)
            #print(avg_volume)           

            #Fetch divident period information
            frequency, dividend_period_multiplier = get_dividend_frequency(ticker)
            #print(frequency)
            #print(dividend_period_multiplier)               

            # Calculate theoretical return based on dividend and price
            theoretical_return = calculate_theoretical_return(investment, median_dividend, current_price, dividend_period_multiplier)
            #print(theoretical_return)

            # Display detailed results
            #display_results(ticker, dividends, median_dividend, theoretical_return, frequency, market_cap, avg_volume)
            result = results_to_excel(ticker, dividends, median_dividend, theoretical_return, frequency,  market_cap, avg_volume, sector, industry)
           # print(result)
            formatted_results.append(result) 

        except Exception as e:
            print(f"Error processing {ticker}: {e}")


    df = combine_df(formatted_results)
#    print(df)

if __name__ == "__main__":
    main()




