import pandas as pd
import openpyxl
from datetime import datetime

current_datetime = datetime.now()
formatted_results = []

def combine_df(formatted_results):

    df = pd.DataFrame(formatted_results)

        # Save the cleaned DataFrame to an Excel file
    file_path = f"output_results_{current_datetime.strftime('%Y%m%d%H%M')}.xlsx"
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    print("Data cleaned and saved to 'output_results.xlsx'")

    return df