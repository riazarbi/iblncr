import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime
from iblncr.client.pricing import get_quotes, get_median_daily_volume, price_portfolio, solve_portfolio

@pytest.fixture
def mock_ib():
    with patch('iblncr.client.pricing.ib_connect') as mock_connect:
        mock_instance = Mock()
        mock_connect.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_ticker():
    mock_contract = Mock()
    mock_contract.conId = 12345
    
    ticker = Mock()
    ticker.contract = mock_contract
    ticker.time = datetime.now()
    ticker.bid = 100.0
    ticker.bidSize = 100
    ticker.ask = 101.0
    ticker.askSize = 200
    ticker.last = 100.5
    ticker.close = 100.0
    ticker.volume = 1000000
    return ticker

@pytest.fixture
def mock_historical_bar():
    bar = Mock()
    bar.volume = 1000000
    return bar

def test_get_quotes(mock_ib, mock_ticker):
    # Setup mocks
    mock_qualified_contract = Mock()
    mock_qualified_contract.conId = 12345
    mock_ib.qualifyContracts.return_value = [mock_qualified_contract]
    mock_ib.reqTickers.return_value = [mock_ticker]
    
    # Test function
    result = get_quotes([12345])
    
    # Verify results
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == [
        'conid', 'quote_time', 'bid_price', 'bid_size', 
        'ask_price', 'ask_size', 'last', 'close', 
        'volume', 'contract'
    ]
    assert result.iloc[0]['conid'] == 12345
    assert result.iloc[0]['bid_price'] == 100.0
    assert result.iloc[0]['ask_price'] == 101.0

def test_get_median_daily_volume(mock_ib, mock_historical_bar):
    # Setup mocks
    mock_qualified_contract = Mock()
    mock_qualified_contract.conId = 12345
    mock_ib.qualifyContracts.return_value = [mock_qualified_contract]
    mock_ib.reqHistoricalData.return_value = [mock_historical_bar] * 10
    
    # Test function
    result = get_median_daily_volume([12345])
    
    # Verify results
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ['conid', 'historical_volume']
    assert result.iloc[0]['conid'] == 12345
    assert result.iloc[0]['historical_volume'] == 1000000

@pytest.fixture
def sample_portfolio_targets():
    return {
        'positions': pd.DataFrame({
            'conid': [1, 2],
            'position': [100, 200],
            'percent_target': [60, 30]
        }).astype({'conid': 'int64'}),  # Ensure conid is int64
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'position': [10000],
            'percent_target': [10]
        }),
        'tolerance': {'percent': 5}
    }

def test_price_portfolio(mock_ib, mock_ticker, sample_portfolio_targets):
    # Setup mocks
    mock_qualified_contract = Mock()
    mock_qualified_contract.conId = 1  # Match the conid in sample_portfolio_targets
    mock_ib.qualifyContracts.return_value = [mock_qualified_contract]
    mock_ib.reqTickers.return_value = [mock_ticker]
    
    # Test function
    result = price_portfolio(sample_portfolio_targets)
    
    # Verify results
    assert isinstance(result, dict)
    assert 'positions' in result
    assert 'cash' in result
    assert 'tolerance' in result
    
    positions = result['positions']
    assert 'price' in positions.columns
    assert 'value_held' in positions.columns
    assert 'percent_held' in positions.columns

def test_solve_portfolio():
    portfolio_priced = {
        'positions': pd.DataFrame({
            'conid': [1, 2],
            'position': [100, 200],
            'percent_target': [60, 30],
            'price': [100, 50],
            'value_held': [10000, 10000],
            'percent_held': [50, 50]
        }),
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'position': [0],
            'percent_target': [10],
            'price': [1],
            'value_held': [0],
            'percent_held': [0]
        }),
        'tolerance': {'percent': 5}
    }
    
    # Test function
    result = solve_portfolio(portfolio_priced)
    
    # Verify results
    assert isinstance(result, dict)
    assert 'positions' in result
    assert 'cash' in result
    
    positions = result['positions']
    assert 'optimal_order' in positions.columns
    assert 'optimal_order_value' in positions.columns
    assert 'out_of_band' in positions.columns
    assert 'percent_deviation' in positions.columns

def test_solve_portfolio_rebalancing_needed():
    # Test case where rebalancing is needed
    portfolio_priced = {
        'positions': pd.DataFrame({
            'conid': [1],
            'position': [100],
            'percent_target': [50],
            'price': [100],
            'value_held': [10000],
            'percent_held': [100]
        }),
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'position': [0],
            'percent_target': [50],
            'price': [1],
            'value_held': [0],
            'percent_held': [0]
        }),
        'tolerance': {'percent': 5}
    }
    
    result = solve_portfolio(portfolio_priced)
    
    # Verify that out_of_band is True and optimal orders are generated
    assert result['positions']['out_of_band'].iloc[0] == True
    assert result['positions']['optimal_order'].iloc[0] < 0  # Should sell to rebalance 