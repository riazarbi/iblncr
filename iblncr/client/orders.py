import pandas as pd
import numpy as np
import time
from ib_async.ib import LimitOrder
from ib_async import Stock
from ib_async import util
from .connection import ib_connect, ib_disconnect
from .pricing import get_quotes, get_median_daily_volume
from typing import Optional

def constrain_orders(portfolio_solved,
                    daily_vol_pct_limit = 0.02,
                    min_order_size = 1000,
                    max_order_size = 10000,
                    buy_only = False,
                    port: int = 4003,
                    account: str = None):
    """Constrain rebalancing orders based on volume and size limits.

    Args:
        portfolio_solved (dict): Portfolio with rebalancing calculations from solve_portfolio()
        daily_vol_pct_limit (float, optional): Maximum percentage of historical daily volume. Defaults to 0.02.
        min_order_size (float, optional): Minimum order value in dollars. Defaults to 1000.
        max_order_size (float, optional): Maximum order value in dollars. Defaults to 10000.
        buy_only (bool, optional): Whether to only allow buy orders. Defaults to False.
        port (int, optional): TWS/Gateway port. Defaults to 4003.

    Returns:
        pd.DataFrame: Constrained orders containing:
            - conid (int): Contract identifier
            - order (float): Order size in shares/contracts
            - value (float): Order value in dollars

    Note:
        Applies volume and size constraints to rebalancing orders:
        1. Limits order size to specified percentage of historical volume
        2. Enforces minimum and maximum order values
        3. Optionally filters out sell orders
        Returns only non-zero orders.
    """
    # extract assets and symbols
    positions = portfolio_solved['positions']

    # Append median historical volumes
    conids = portfolio_solved["positions"]["conid"].tolist()
    volumes = get_median_daily_volume(conids, days = 10, port = port, account = account)
    positions = pd.merge(positions, volumes, on='conid', how='left')


    # work out the per-symbol constraints
    positions['volume_constraint'] = np.floor(positions.historical_volume.mul(daily_vol_pct_limit))
    positions['max_value_constraint'] = max_order_size
    positions['min_value_constraint'] = min_order_size

    # work out the constrained trade value
    positions['value'] = np.minimum(abs(positions.optimal_order_value), positions.max_value_constraint)
    positions['value'] = positions['value'].where(positions['value'] > positions['min_value_constraint'], 0)
    # work out constrained order size
    positions['order'] = np.floor(np.minimum(positions.volume_constraint, positions.value / positions.price))

    # recompute the constrained value for rounding issues
    positions.value = positions.order * positions.price

    # correct the sign for sell orders
    positions.value = np.where(positions['optimal_order_value'] < 0, -positions['value'], positions['value'])
    positions.order = np.where(positions['optimal_order'] < 0, -positions['order'], positions['order'])

    # drop sells if buy only constraint
    if buy_only:
        # Apply the conditions to 'order' and 'value' columns
        positions['order'] = np.where(positions['order'] < 0, 0, positions['order'])
        positions['value'] = np.where(positions['value'] < 0, 0, positions['value'])
    
    positions = positions[(positions["order"] != 0) | (positions["value"] != 0)]
    
    orders = positions[['conid', 'order', 'value']]
    return(orders)


def price_orders(order_quantities,
                 spread_tolerance = 0.02,
                 port: int = 4003,
                 account: str = None):
    """Price orders using current market quotes.

    Gets current market quotes for the order conids and calculates limit prices
    at the midpoint between bid and ask. Filters out quotes with invalid or
    missing prices, or spreads wider than the tolerance.

    Args:
        order_quantities (DataFrame): DataFrame containing order quantities with columns:
            - conid (int): Contract identifier
            - order (float): Order size in shares/contracts
        spread_tolerance (float, optional): Maximum allowable bid-ask spread as a 
            percentage of ask price. Defaults to 0.02 (2%).
        port (int, optional): TWS/Gateway port number. Defaults to 4003.

    Returns:
        DataFrame: Original order quantities with added columns:
            - limit (float): Calculated limit price (midpoint)
            - value (float): Order value (quantity * limit price)
    """
    
    if len(order_quantities) == 0:
        print("No order quantities to price")
        return None
    
    quotes_unfiltered = get_quotes(order_quantities.conid.tolist(), port=port, account=account)

    quotes_unfiltered = quotes_unfiltered[~quotes_unfiltered[['bid_price', 'ask_price', 'bid_size', 'ask_size']].isin([-1, 0]).any(axis=1)]
    quotes = quotes_unfiltered.dropna(subset=['bid_price', 'ask_price', 'bid_size', 'ask_size'])

    # Create a new DataFrame instead of modifying a view
    if len(quotes) > 0:
        quotes['spread'] = (quotes['ask_price'] - quotes['bid_price']) / quotes['ask_price']
        quotes = quotes[quotes['spread'] < spread_tolerance]
        quotes['limit'] = (quotes['ask_price'] + quotes['bid_price']) / 2
        quotes = quotes[['conid', 'limit']]

        orders = pd.merge(order_quantities, quotes, on='conid', how='left')
        orders.limit = round(orders.limit, 2)
        orders['value'] = orders.order * orders.limit
    
        return orders
    else:
        print("No quotes found for orders quantities.")
        return None
    

def submit_orders(orders, port: int = 4003, account: str = None):
    """Submit limit orders to Interactive Brokers.

    Creates IB contract objects from conids, qualifies them with the IB API,
    and submits limit orders based on the calculated prices and quantities.
    Buy orders are created for positive values, sell orders for negative values.

    Args:
        orders (DataFrame): DataFrame containing order details with columns:
            - conid (int): Contract identifier
            - order (float): Order size in shares/contracts 
            - limit (float): Limit price
            - value (float): Order value (quantity * limit price)
        port (int, optional): TWS/Gateway port number. Defaults to 4003.

    Returns:
        None
    """
    ib = ib_connect(port=port, account=account)
    contracts = [Stock(conId=i) for i in orders.conid.tolist()]
    all = ib.qualifyContracts(*contracts)    
    orders['contract'] = all

    orders['ib_order'] = orders.apply(lambda row: LimitOrder('SELL' if row['value'] < 0 else 'BUY', 
                                              abs(row['order']), row['limit']), axis=1)

    submissions = []
    for _, row in orders.iterrows():
        contract = row['contract']
        order = row['ib_order']
        trade = ib.placeOrder(contract, order)
        submissions.append(trade)
        
    ib_disconnect(ib)


def get_orders(port: int = 4003, account: str = None):
    """Get all open orders from Interactive Brokers.

    Connects to TWS/Gateway, retrieves all open orders, and disconnects.

    Args:
        port (int, optional): TWS/Gateway port number. Defaults to 4003.

    Returns:
        list: List of open IB order objects
    """
    ib = ib_connect(port = port, account = account)
    orders = ib.orders()
    
    ib_disconnect(ib)
    return util.df(orders)


def get_filled_orders(port: int = 4003, account: str = None):
    """Get all filled orders from the current Interactive Brokers session.

    Connects to TWS/Gateway, retrieves all filled trades from the current session,
    and disconnects.

    Args:
        port (int, optional): TWS/Gateway port number. Defaults to 4003.
        account (str, optional): IB account to use. Defaults to None.

    Returns:
        pd.DataFrame: DataFrame of filled orders containing:
            - orderId: The IB order identifier
            - time: Fill timestamp
            - symbol: Contract symbol
            - side: BUY/SELL
            - quantity: Number of shares/contracts filled
            - avgFillPrice: Average fill price
            - commission: Trade commission
    """
    ib = ib_connect(port=port, account=account)
    # Get filled trades from current session
    filled_trades = ib.fills()
    
    ib_disconnect(ib)
    # Convert to DataFrame with relevant columns
    filled_orders = util.df(filled_trades)
    if filled_orders is None:
        return None
    elif len(filled_orders) == 0:
        return None
    else:
        return filled_orders


def cancel_orders(port: int = 4003, account: str = None):
    """Cancel all open orders at Interactive Brokers.

    Connects to TWS/Gateway, cancels all open orders, and disconnects.

    Args:
        port (int, optional): TWS/Gateway port number. Defaults to 4003.

    Returns:
        None
    """
    ib = ib_connect(port = port, account = account)
    ib.reqGlobalCancel()
    ib_disconnect(ib)

def execute_orders(orders: pd.DataFrame, account: str, port: int = 4003) -> Optional[pd.DataFrame]:
    """Execute orders and handle the order lifecycle."""
    if orders is None:
        print("Failed to price orders")
        return None

    print("Submitting orders")
    submit_orders(orders, account=account, port=port)     
    
    print("Waiting 60 seconds before cancelling unfilled orders")
    time.sleep(60)

    print("Getting filled orders")
    filled_orders = get_filled_orders(account=account, port=port)
    
    print("Cancelling remaining orders\n")
    cancel_orders(account=account, port=port)
    
    return filled_orders
