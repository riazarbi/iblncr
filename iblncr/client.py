from ib_async.ib import IB, LimitOrder
from ib_async import Stock
import pandas as pd
import numpy as np
import yaml
import time

def ib_connect(host: str = "127.0.0.1", port: int = 4003, client_id: int = 1):
    """
    Establishes a connection to Interactive Brokers TWS/Gateway.
    
    Args:
        host (str, optional): The hostname or IP address of the TWS/Gateway. Defaults to "127.0.0.1".
        port (int, optional): The port number to connect to. Defaults to 4003.
        client_id (int, optional): A unique client identifier. Defaults to 1.
    
    Returns:
        IB: An initialized and connected IB client instance.
        
    Note:
        - The connection is blocking until established
        - Market data type is set to delayed frozen data (type 3)
    """
    ib = IB()
    ib.connect(host, port, client_id)  # Now a blocking call
    ib.reqMarketDataType(3)
    return(ib)


def ib_disconnect(ib):
    """
    Disconnects from the Interactive Brokers TWS/Gateway.
    
    Args:
        ib (IB): The IB client instance to disconnect.

    """
    ib.disconnect()


def get_ib_server_time(port: int = 4003):
        """
        Gets the current server time from Interactive Brokers TWS/Gateway.
        
        Args:
            port (int, optional): The port number to connect to. Defaults to 4003.
            
        Returns:
            datetime: The current server time from IB.
            
        Note:
            This function handles the connection and disconnection to IB automatically.
        """
        ib = ib_connect(port = port)
        time_str = ib.reqCurrentTime()
        ib_disconnect(ib)
        return time_str


def get_cash(account, port: int = 4003):
    """
    Retrieves the cash balance for a specified account from Interactive Brokers.
    
    Args:
        account (str): The IB account identifier to query.
        port (int, optional): The port number to connect to. Defaults to 4003.
        
    Returns:
        pd.DataFrame: A DataFrame containing:
            - currency (str): The currency code (USD)
            - position (float): The cash balance amount
            
    Raises:
        ValueError: If account argument is None
        
    Note:
        This function handles the connection and disconnection to IB automatically.
    """
    if account is None:
        raise ValueError("account argument should not be None")
    ib = ib_connect(port = port)
    cash = [x.value for x in ib.accountValues(account = account) if x.tag == "CashBalance" and x.currency == "USD"][0]
    ib_disconnect(ib)
    data = [{"currency": "USD", "position": cash}]
    df = pd.DataFrame(data)
    df["position"] = pd.to_numeric(df["position"])    
    return df


def get_positions(account, port: int = 4003):
    """
    Retrieves current positions for a specified account from Interactive Brokers.
    
    Args:
        account (str): The IB account identifier to query.
        port (int, optional): The port number to connect to. Defaults to 4003.
        
    Returns:
        pd.DataFrame: A DataFrame containing:
            - conid (int): The contract identifier
            - position (float): The quantity held
            - ave_cost (float): The average cost basis
            
    Raises:
        ValueError: If account argument is None
        
    Note:
        This function handles the connection and disconnection to IB automatically.
    """
    if account is None:
        raise ValueError("account argument should not be None")
    ib = ib_connect(port = port)
    positions = ib.positions(account = account)
    ib_disconnect(ib)
    df = pd.DataFrame([
        {
            "conid": t.contract.conId,
            "position": t.position,
            "ave_cost": t.avgCost
        }
        for t in positions
    ])    
    return df


def get_portfolio_state(account, port: int = 4003):
    """
    Retrieves the current portfolio state from Interactive Brokers, including cash and positions.

    Args:
        account (str): The IB account identifier to query.
        port (int, optional): The port number to connect to. Defaults to 4003.

    Returns:
        dict: A dictionary containing:
            - cash (pd.DataFrame): Cash balance information from get_cash()
            - positions (pd.DataFrame): Position information from get_positions()

    Raises:
        ValueError: If account argument is None (inherited from get_cash/get_positions)

    Note:
        This function handles the connection and disconnection to IB automatically through
        its constituent functions get_cash() and get_positions().
    """
    portfolio = {"cash": get_cash(account = account), "positions": get_positions(account = account, port = port)}
    return(portfolio)


def get_portfolio_model(path, port: int = 4003):
    """
    Loads a portfolio model from a YAML file and enriches it with contract IDs from Interactive Brokers.

    Args:
        path (str): Path to the YAML file containing the portfolio model
        port (int, optional): The port number to connect to. Defaults to 4003.

    Returns:
        dict: A dictionary containing the portfolio model with:
            - positions (pd.DataFrame): Position information with contract IDs
            - cash (dict): Cash allocation information
            - tolerance (float): Portfolio rebalancing tolerance

    Raises:
        FileNotFoundError: If the YAML file does not exist
        yaml.YAMLError: If there are errors parsing the YAML file

    Note:
        This function handles the connection and disconnection to IB automatically.
        The input YAML file should contain positions with symbol, exchange, and currency fields.
    """
    with open(path, "r") as file:
        portfolio_model = yaml.safe_load(file)  # Use safe_load to avoid security risks

    df = pd.DataFrame(portfolio_model["positions"])
    df['contract'] = df.apply(lambda row: Stock(row.symbol, row.exchange, row.currency), axis=1)    
    ib = ib_connect(port = port)
    df['contract'] = ib.qualifyContracts(*df['contract'])
    ib_disconnect(ib)
    df['conid'] = df.apply(lambda row: row.contract.conId, axis=1)
    df = df.drop(['contract', 'symbol', 'exchange', 'currency'], axis=1)
    portfolio_model['positions'] = df
    return(portfolio_model) 
    

def load_portfolio_targets(portfolio_state, portfolio_model):
    """
    Combines current portfolio state with target model to create portfolio targets.

    Args:
        portfolio_state (dict): Current portfolio state containing:
            - positions (pd.DataFrame): Current position information
            - cash (pd.DataFrame): Current cash balance information
        portfolio_model (dict): Target portfolio model containing:
            - positions (pd.DataFrame): Target position allocations
            - cash (dict): Target cash allocation
            - tolerance (float): Portfolio rebalancing tolerance

    Returns:
        dict: Portfolio targets containing:
            - positions (pd.DataFrame): Combined current and target position information
            - cash (pd.DataFrame): Cash information with target allocation
            - tolerance (float): Portfolio rebalancing tolerance

    Note:
        The function merges current positions with target allocations, filling missing
        values with 0 and renaming the target allocation column to 'percent_target'.
    """
    state = portfolio_state['positions']
    model = portfolio_model['positions']
        
    targets = pd.merge(state, model, how = 'outer', on=['conid'])
    targets = targets.fillna(0)
    targets = targets.rename(columns={"percent": "percent_target"})

    cash = portfolio_state['cash']
    cash['percent_target'] = portfolio_model['cash']['percent']
    tolerance = portfolio_model['tolerance']

    portfolio_targets = {"cash": cash, "positions": targets, "tolerance": tolerance}
    return(portfolio_targets)


def get_quotes(conids, port: int = 4003):
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
    ib = ib_connect(port = port)
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
  
  
def get_median_daily_volume(conids, days = 10, port: int = 4003):
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
    ib = ib_connect(port = port)
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


def price_portfolio(portfolio_targets, port: int = 4003):
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
    prices = get_quotes(conids, port = port)    
    assets = pd.merge(portfolio_targets['positions'],prices, on='conid', how='left')
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

    portfolio_priced['cash'] = cash
    portfolio_priced['positions'] = positions

    return(portfolio_priced)
    

    

def constrain_orders(portfolio_solved,
                    daily_vol_pct_limit = 0.02,
                    min_order_size = 1000,
                    max_order_size = 10000,
                    buy_only = False,
                    port: int = 4003):
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
    conids = portfolio_targets["positions"]["conid"].tolist()
    volumes = get_median_daily_volume(conids, days = 10, port = port)
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
                 port: int = 4003):
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
    quotes = get_quotes(order_quantities.conid.tolist(), port = port)

    quotes = quotes[~quotes[['bid_price', 'ask_price', 'bid_size', 'ask_size']].isin([-1, 0]).any(axis=1)]

    # Drop rows where any of the specified columns are NA (if needed)
    quotes = quotes.dropna(subset=['bid_price', 'ask_price', 'bid_size', 'ask_size'])

    # Check if DataFrame is not empty, calculate spread and filter based on condition
    if len(quotes) > 0:
        quotes['spread'] = (quotes['ask_price'] - quotes['bid_price']) / quotes['ask_price']
        quotes = quotes[quotes['spread'] < spread_tolerance]

    # Check if quotes DataFrame is not empty
    if len(quotes) > 0:
        quotes['limit'] = (quotes['ask_price'] + quotes['bid_price']) / 2
        quotes = quotes[['conid', 'limit']]  # Select only 'symbol' and 'limit'
    else:
        quotes = order_quantities[['conid']]  # Select only 'symbol'
        quotes['limit'] = np.nan  # Add 'limit' column with NA (NaN)

    orders = pd.merge(order_quantities, quotes, on='conid', how='left')
    orders.limit = round(orders.limit, 2)
    orders['value'] = orders.order * orders.limit
    
    return(orders)


def submit_orders(orders, port: int = 4003):
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
    ib = ib_connect(port = port)
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


def get_orders(port: int = 4003):
    """Get all open orders from Interactive Brokers.

    Connects to TWS/Gateway, retrieves all open orders, and disconnects.

    Args:
        port (int, optional): TWS/Gateway port number. Defaults to 4003.

    Returns:
        list: List of open IB order objects
    """
    ib = ib_connect(port = port)
    orders = ib.orders()
    ib_disconnect(ib)
    return orders


def cancel_orders(port: int = 4003):
    """Cancel all open orders at Interactive Brokers.

    Connects to TWS/Gateway, cancels all open orders, and disconnects.

    Args:
        port (int, optional): TWS/Gateway port number. Defaults to 4003.

    Returns:
        None
    """
    ib = ib_connect(port = port)
    ib.reqGlobalCancel()
    ib_disconnect(ib)


portfolio_model = get_portfolio_model("iblncr/data/sample_model.yaml")
portfolio_state = get_portfolio_state()
portfolio_state['positions']
portfolio_targets = load_portfolio_targets(portfolio_state, portfolio_model)
portfolio_targets['positions']

portfolio_priced = price_portfolio(portfolio_targets)
portfolio_priced['cash']
portfolio_priced['positions']

portfolio_solved = solve_portfolio(portfolio_priced)

out_of_band = any([any(portfolio_solved['cash'].out_of_band), any(portfolio_solved['positions'].out_of_band)])

if out_of_band:
    order_quantities = constrain_orders(portfolio_solved)
    orders = price_orders(order_quantities)
    orders
    submit_orders(orders)
    time.sleep(30)
    cancel_orders()
else: 
    print("Porfolio weights are within tolerance. Exiting")