import pandas as pd
import openpyxl

def display_results(ticker, dividends, median_dividend, theoretical_return, frequency, market_cap, avg_volume, sector, industry):
    """
    Display detailed results including dividend data and calculations.

    Parameters:
        ticker (str): Stock ticker symbol.
        dividends (pandas.Series): Dividend payments within the last year.
        median_dividend (float): Median dividend value.
        theoretical_return (float): Theoretical return on investment.
    """
    print(f"Results for {ticker}:")
#    print("Dividend Data (Last Year):")
#    print(dividends)
    print(f"Median Dividend: {median_dividend:.2f}")
    print(f"Theoretical Return on $1000 Investment: ${theoretical_return:.2f}")
#    print(frequency)
    print(f"Market Capitalization: {market_cap}")
    print(f"Average Volume: {avg_volume}")

def results_to_excel(ticker, dividends, median_dividend, theoretical_return, frequency, market_cap, avg_volume, sector, industry):



    result = {
        "Ticker": ticker,
        "Theoretical Return": theoretical_return,
        "Median Dividend": median_dividend,
        "Market Capitalization": market_cap,
        "Average Volume": avg_volume,
        "Dividend frequency": frequency,
        "Sector": sector,
        "Industry": industry
    }
    
    return result

#    df = pd.DataFrame(formatted_results)
#    print(df)

    # Save the cleaned DataFrame to an Excel file
#    file_path = 'output_results.xlsx'
#    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
#        df.to_excel(writer, index=False, sheet_name='Results')

#    print("Data cleaned and saved to 'output_results.xlsx'")