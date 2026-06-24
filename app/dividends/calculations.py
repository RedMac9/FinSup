def calculate_theoretical_return(investment, median_dividend, current_price, dividend_period_multiplier):
    """
    Calculate theoretical return based on an investment, median dividend, and current stock price.

    Parameters:
        investment (float): Amount invested.
        median_dividend (float): Median dividend value.
        current_price (float): Current price of the stock.

    Returns:
        float: Theoretical return.
    """
    if current_price is None or current_price <= 0:
        raise ValueError("Invalid current price for stock.")
    
    # Calculate number of shares that can be purchased with the investment
    shares = investment / current_price
    
    # Calculate theoretical return based on median dividend and shares
    return shares * median_dividend * dividend_period_multiplier / 12