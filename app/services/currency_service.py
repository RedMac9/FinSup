import requests
from typing import Dict, Tuple, Optional, Any
import csv

def fetch_nbp_table_a_rates() -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Fetches the entire 'A' table of exchange rates from the NBP API.

    Returns:
        A tuple containing (rates_dictionary, effective_date) if successful, else None.
        The dictionary is keyed by currency code (e.g., 'USD').
    """
    url = "http://api.nbp.pl/api/exchangerates/tables/a/?format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        # The response is a list with one element which is the table
        table_data = data[0]
        effective_date = table_data.get('effectiveDate')
        rates_list = table_data.get('rates', [])

        if not effective_date or not rates_list:
            print("Error: 'effectiveDate' or 'rates' not found in API response.")
            return None

        # Create a more accessible dictionary from the list of rates
        rates_map = {rate['code']: rate for rate in rates_list}
        return rates_map, effective_date

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching data from the NBP API: {e}")
        return None
    except (IndexError, KeyError, TypeError) as e:
        print(f"Error parsing NBP API response: {e}")
        return None

def get_and_display_nbp_rates():
    """
    Fetches and displays exchange rates for a predefined list of currencies.
    """
    target_currencies = ['USD', 'CAD', 'EUR', 'CHF', 'GBP', 'JPY']
    result = fetch_nbp_table_a_rates()

    if result:
        rates_map, effective_date = result
        print(f"\n--- NBP Exchange Rates (Table A) for {effective_date} ---")
        print(f"{'Nazwa waluty':<25} {'Kod waluty':<12} {'Kurs średni (PLN)'}")
        print("-" * 60)

        for code in target_currencies:
            if code in rates_map:
                rate_info = rates_map[code]
                currency_name = rate_info['currency']
                rate = rate_info['mid']
                # Handle JPY which is quoted per 100 units
                prefix = "100" if code == 'JPY' else "1"
                print(f"{currency_name:<25} {prefix + ' ' + code:<12} {rate:.4f}")
            else:
                print(f"{'N/A':<25} {code:<12} Not found in table A")
        print("-" * 60 + "\n")
    else:
        print("Could not retrieve exchange rate.")

def save_rates_to_csv(file_path: str, rates_map: Dict[str, Any], effective_date: str, target_currencies: Optional[list[str]] = None):
    """
    Saves the provided NBP exchange rates to a CSV file.

    The CSV file will have the columns: 'currency', 'rate', 'date'.

    Args:
        file_path (str): The path to the output CSV file.
        rates_map (Dict[str, Any]): A dictionary of rates keyed by currency code.
        effective_date (str): The effective date for the rates.
        target_currencies (Optional[list[str]]): A list of currency codes to save.
                                                 If None, all currencies will be saved.
    """
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['currency', 'rate', 'date']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()

            currencies_to_save = target_currencies if target_currencies is not None else rates_map.keys()

            for code in currencies_to_save:
                if code in rates_map:
                    rate_info = rates_map[code]
                    writer.writerow({'currency': code, 'rate': rate_info['mid'], 'date': effective_date})
        print(f"Successfully saved rates for {effective_date} to {file_path}")
    except IOError as e:
        print(f"Error writing to file {file_path}: {e}")