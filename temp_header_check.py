import pandas as pd

filename = 'app/tests/ETF.csv'

try:
    # Read the csv with utf-8 encoding and print the header
    df = pd.read_csv(filename, sep=';', encoding='utf-8')
    print(df.columns.tolist())

except FileNotFoundError:
    print(f"Error: '{filename}' not found.")
except Exception as e:
    print(f"An error occurred: {e}")