import pandas as pd
import yaml
from ib_async import Stock
from .connection import ib_connect, ib_disconnect

def get_cash(port: int = 4003):
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
    ib = ib_connect(port = port)
    cash = [x.value for x in ib.accountValues() if x.tag == "CashBalance" and x.currency == "USD"][0]
    ib_disconnect(ib)
    data = [{"currency": "USD", "position": cash}]
    df = pd.DataFrame(data)
    df["position"] = pd.to_numeric(df["position"])    
    return df


def get_positions(port: int = 4003):
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
    ib = ib_connect(port = port)
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


def get_portfolio_state(port: int = 4003):
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
    portfolio = {"cash": get_cash(port=port), "positions": get_positions(port=port)}
    return portfolio


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
