import pandas as pd
import numpy as np
from .connection import ib_connect, ib_disconnect
from ib_async import Stock

def get_quotes(conids, port: int = 4003, account: str = None):
    """
    Retrieves real-time market quotes for a list of contract IDs.

    Args:
        conids (list): List of contract IDs to get quotes for
        port (int, optional): Port number for IB connection. Defaults to 4003.

    Returns:
        pd.DataFrame: DataFrame containing quote information with columns:
            - conid (int): Contract ID
            - quote_time (datetime): Time of the quote
            - bid_price (float): Current bid price
            - bid_size (int): Size of bid
            - ask_price (float): Current ask price 
            - ask_size (int): Size of ask
            - last (float): Last traded price
            - close (float): Previous close price
            - volume (int): Trading volume
            - contract (Contract): IB contract object

    Note:
        Connects to Interactive Brokers, qualifies the contracts, retrieves ticker data,
        and disconnects. Returns data in a pandas DataFrame format.
    """
    ib = ib_connect(port = port, account = account)
    contracts = [Stock(conId=i) for i in conids]
    all = ib.qualifyContracts(*contracts)    
    tickers = [ib.reqTickers(*all)]
    ib_disconnect(ib)
    df = pd.DataFrame([
        {
            "conid": t.contract.conId,
            "quote_time": t.time,
            "bid_price": t.bid,
            "bid_size": t.bidSize,
            "ask_price": t.ask,
            "ask_size": t.askSize,
            "last": t.last,
            "close": t.close,
            "volume": t.volume,
            "contract": t.contract
        }
        for sublist in tickers for t in sublist  # Flatten the list
    ])    
    return df
  
  
def get_median_daily_volume(conids, days = 10, port: int = 4003, account: str = None):
    """
    Retrieves historical daily volume data and calculates the median daily volume for a list of contract IDs.

    Args:
        conids (list): List of contract IDs to get volume data for
        days (int, optional): Number of days of historical data to retrieve. Defaults to 10.
        port (int, optional): Port number for IB connection. Defaults to 4003.

    Returns:
        pd.DataFrame: DataFrame containing volume information with columns:
            - conid (int): Contract ID
            - historical_volume (float): Median daily trading volume over the specified period

    Note:
        Connects to Interactive Brokers, qualifies the contracts, retrieves historical daily
        volume data, calculates the median, and disconnects. Returns data in a pandas DataFrame format.
    """
    ib = ib_connect(port = port, account = account)
    contracts = [Stock(conId=i) for i in conids]
    all = ib.qualifyContracts(*contracts)    
    average_volume = []

    for al in all:
        bars = ib.reqHistoricalData(
            al,
            endDateTime='',
            durationStr=f'{days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True
        )
    
        # Sum the volume for the 10-day period
        med_vol = np.median([bar.volume for bar in bars])
    
        average_volume.append({"conid": al.conId, "historical_volume": med_vol})

    ib_disconnect(ib)
    df = pd.DataFrame(average_volume)
    return df


def price_portfolio(portfolio_targets, port: int = 4003, account: str = None):
    """
    Prices a portfolio by getting current market prices and calculating position values and percentages.

    Args:
        portfolio_targets (dict): Portfolio specification containing:
            - positions (pd.DataFrame): Asset positions with columns:
                - conid (int): Contract IDs
                - position (float): Current position sizes
                - percent_target (float): Target percentage allocations
            - cash (pd.DataFrame): Cash position information
            - tolerance (dict): Rebalancing tolerance parameters
        port (int, optional): Port number for IB connection. Defaults to 4003.

    Returns:
        dict: Priced portfolio containing:
            - positions (pd.DataFrame): Asset positions with additional columns:
                - price (float): Current market prices
                - value_held (float): Current position values
                - percent_held (float): Current percentage allocations
            - cash (pd.DataFrame): Cash position with pricing info
            - tolerance (dict): Original tolerance parameters

    Note:
        Gets current market prices via IB, calculates position values and percentages,
        and returns enriched portfolio data structure for downstream rebalancing.
    """
    # Positions
    conids = portfolio_targets["positions"]["conid"].tolist()
    prices = get_quotes(conids, port=port, account=account)    
    assets = pd.merge(portfolio_targets['positions'], prices, on='conid', how='left')
    assets['price'] = assets.close
    assets['value_held'] = assets.position * assets.price
    
    # Cash
    cash = portfolio_targets['cash']
    cash['price'] = 1
    cash['value_held'] = cash.position * cash.price

    # Math
    total_value  = cash.value_held + sum(assets.value_held)
    assets['percent_held'] = assets.value_held.div(total_value[0]).mul(100).round(2)
    cash['percent_held'] = cash.value_held.div(total_value[0]).mul(100).round(2)
    
    # Keep only relevant columns for downstream processing
    assets = assets[['conid', 'position', 'percent_target', 'price', 'value_held', 'percent_held']]
    
    # Build
    portfolio = {"cash": cash, "positions": assets, "tolerance": portfolio_targets["tolerance"]}
    return(portfolio)


def solve_portfolio(portfolio_priced):
    """
    Calculates target positions and optimal orders to rebalance a portfolio.

    Args:
        portfolio_priced (dict): Priced portfolio containing:
            - positions (pd.DataFrame): Asset positions with pricing info
            - cash (pd.DataFrame): Cash position with pricing info 
            - tolerance (dict): Rebalancing tolerance parameters

    Returns:
        dict: Portfolio with rebalancing calculations containing:
            - positions (pd.DataFrame): Asset positions with additional columns:
                - value_target (float): Target position values
                - position_target (float): Target position sizes
                - percent_deviation (float): Deviation from target percentages
                - out_of_band (bool): Whether position exceeds tolerance
                - optimal_order (float): Order size to reach target
                - optimal_order_value (float): Value of optimal order
            - cash (pd.DataFrame): Cash position with rebalancing info
            - tolerance (dict): Original tolerance parameters

    Note:
        Calculates target positions and optimal orders to rebalance portfolio to target allocations,
        subject to specified tolerance bands. Returns enriched portfolio data structure for order generation.
    """
    cash = portfolio_priced['cash']
    positions = portfolio_priced['positions']
    total_value  = cash.value_held + sum(positions.value_held)

    cash['value_target'] = cash.percent_target.div(100).mul(total_value[0])
    positions['value_target'] = positions.percent_target.div(100).mul(total_value[0])

    positions['position_target'] = np.floor(positions.value_target / positions.price)
    cash['position_target'] = np.floor(cash.value_target / cash.price)

    positions['percent_deviation'] = abs((positions.value_held - positions.value_target) / positions.value_target) * 100
    cash['percent_deviation'] = abs((cash.value_held - cash.value_target) / cash.value_target) * 100

    positions['out_of_band'] = positions["percent_deviation"].gt(portfolio_priced["tolerance"]['percent'])
    cash['out_of_band'] = cash["percent_deviation"].gt(portfolio_priced["tolerance"]['percent'])

    positions['optimal_order'] = positions.position_target - positions.position
    positions['optimal_value'] = (positions.position + positions.optimal_order) * positions.price
    positions['optimal_order_value'] = positions.price * positions.optimal_order

    post_rebalancing_cash_balance = total_value - sum(positions.optimal_value)
    cash['optimal_value'] = post_rebalancing_cash_balance

    positions = positions[['conid', 'percent_held', 'percent_target', 'position', 'position_target', 'percent_deviation', 'price', 'optimal_order', 'optimal_order_value', 'out_of_band']]
    cash = cash[['currency', 'percent_held', 'percent_target', 'position', 'position_target', 'percent_deviation', 'price', 'optimal_value', 'out_of_band']]

    portfolio_priced['cash'] = cash
    portfolio_priced['positions'] = positions

    return(portfolio_priced)