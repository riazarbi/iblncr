import pandas as pd
import yaml
from ib_async import Stock
from .connection import ib_connect, ib_disconnect
from datetime import datetime

def get_cash(port: int = 4003, account: str = None):
    """
    Retrieves the cash balance from Interactive Brokers.
    
    Args:
        port (int, optional): The port number to connect to. Defaults to 4003.
        
    Returns:
        pd.DataFrame: A DataFrame containing:
            - currency (str): The currency code (USD)
            - position (float): The cash balance amount
            
    Note:
        This function handles the connection and disconnection to IB automatically.
    """
    ib = ib_connect(port = port, account = account)
    cash = [x.value for x in ib.accountValues() if x.tag == "CashBalance" and x.currency == "USD"][0]
    ib_disconnect(ib)
    data = [{"currency": "USD", "position": cash}]
    df = pd.DataFrame(data)
    df["position"] = pd.to_numeric(df["position"])    
    return df


def get_positions(port: int = 4003, account: str = None):
    """
    Retrieves current positions from Interactive Brokers.
    
    Args:
        port (int, optional): The port number to connect to. Defaults to 4003.
        
    Returns:
        pd.DataFrame: A DataFrame containing:
            - conid (int): The contract identifier
            - position (float): The quantity held
            - ave_cost (float): The average cost basis
            
    Note:
        This function handles the connection and disconnection to IB automatically.
    """
    ib = ib_connect(port = port, account = account)
    positions = ib.positions()
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


def get_portfolio_state(port: int = 4003, account: str = None):
    """
    Retrieves the current portfolio state from Interactive Brokers, including cash and positions.

    Args:
        port (int, optional): The port number to connect to. Defaults to 4003.

    Returns:
        dict: A dictionary containing:
            - cash (pd.DataFrame): Cash balance information from get_cash()
            - positions (pd.DataFrame): Position information from get_positions()

    Note:
        This function handles the connection and disconnection to IB automatically through
        its constituent functions get_cash() and get_positions().
    """
    portfolio = {
        "cash": get_cash(port=port, account=account), 
        "positions": get_positions(port=port, account=account)
    }
    return portfolio


def create_model_from_portfolio(portfolio_state, file_path='model.yaml', port: int = 4003, account: str = None):
    # Extract cash and positions from portfolio_state
    positions_df = portfolio_state['positions']

    ib = ib_connect(port = port, account = account)
    conids = positions_df.conid
    contracts = [Stock(conId=i) for i in conids]
    stocks = ib.qualifyContracts(*contracts)    
    ib_disconnect(ib)
    symbols = [stock.symbol for stock in stocks]
    exchanges = [stock.exchange for stock in stocks]
    currencies = [stock.currency for stock in stocks]
    positions_df.insert(0, 'currency', currencies)
    positions_df.insert(0, 'exchange', exchanges)
    positions_df.insert(0, 'symbol', symbols)


    # Create the YAML structure using a standard dictionary
    model_data = {
        'name': 'generated_portfolio',
        'description': 'Generated from portfolio state',
        'cash': {'percent': 5},  # Hardcoded to 5%
        'positions': [],
        'tolerance': {'percent': 5},  # Assuming a default value, adjust as needed
        'cooldown': {'days': 365},  # Assuming a default value, adjust as needed
        'buy_only': False,  # Assuming a default value, adjust as needed
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    # Populate positions
    for _, row in positions_df.iterrows():
        model_data['positions'].append({
            'symbol': str(row['symbol']),  # Ensure symbol is a string
            'exchange': str(row['exchange']),  # Assuming a default value, adjust as needed
            'currency': str(row['currency']),  # Assuming a default value, adjust as needed
            'percent': 0  # Evenly split percentage
        })

    # Write to YAML file
    with open(file_path, 'w') as file:
        yaml.dump(model_data, file, default_flow_style=False, sort_keys=False)


def get_portfolio_model(path, port: int = 4003, account: str = None):
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
    ib = ib_connect(port = port, account = account)
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

