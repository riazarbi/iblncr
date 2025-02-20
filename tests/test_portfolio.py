import pytest
import pandas as pd
from unittest.mock import Mock, patch, mock_open
from iblncr.client.portfolio import (
    get_cash, get_positions, get_portfolio_state, 
    get_portfolio_model, load_portfolio_targets
)

@pytest.fixture
def mock_ib():
    with patch('iblncr.client.portfolio.ib_connect') as mock_connect:
        mock_instance = Mock()
        mock_connect.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def sample_account_value():
    mock_value = Mock()
    mock_value.tag = "CashBalance"
    mock_value.currency = "USD"
    mock_value.value = "10000.50"
    return mock_value

@pytest.fixture
def sample_position():
    mock_position = Mock()
    mock_position.contract.conId = 12345
    mock_position.position = 100
    mock_position.avgCost = 50.25
    return mock_position

def test_get_cash(mock_ib, sample_account_value):
    # Setup mock
    mock_ib.accountValues.return_value = [sample_account_value]
    
    # Test function
    result = get_cash(port=4003)
    
    # Verify results
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ['currency', 'position']
    assert result.iloc[0]['currency'] == 'USD'
    assert result.iloc[0]['position'] == 10000.50
    
    # Verify mock calls
    mock_ib.accountValues.assert_called_once()

def test_get_positions(mock_ib, sample_position):
    # Setup mock
    mock_ib.positions.return_value = [sample_position]
    
    # Test function
    result = get_positions(port=4003)
    
    # Verify results
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ['conid', 'position', 'ave_cost']
    assert result.iloc[0]['conid'] == 12345
    assert result.iloc[0]['position'] == 100
    assert result.iloc[0]['ave_cost'] == 50.25
    
    # Verify mock calls
    mock_ib.positions.assert_called_once()

def test_get_portfolio_state(mock_ib, sample_account_value, sample_position):
    # Setup mocks
    mock_ib.accountValues.return_value = [sample_account_value]
    mock_ib.positions.return_value = [sample_position]
    
    # Test function
    result = get_portfolio_state(port=4003)
    
    # Verify results
    assert isinstance(result, dict)
    assert 'cash' in result
    assert 'positions' in result
    assert isinstance(result['cash'], pd.DataFrame)
    assert isinstance(result['positions'], pd.DataFrame)

@patch('builtins.open', new_callable=mock_open, read_data="""
positions:
  - symbol: AAPL
    exchange: NASDAQ
    currency: USD
    percent: 0.5
cash:
  percent: 0.5
tolerance: 0.1
""")
def test_get_portfolio_model(mock_file, mock_ib):
    # Setup mock for contract qualification
    mock_contract = Mock()
    mock_contract.conId = 12345
    mock_ib.qualifyContracts.return_value = [mock_contract]
    
    # Test function
    result = get_portfolio_model("dummy_path.yaml")
    
    # Verify results
    assert isinstance(result, dict)
    assert 'positions' in result
    assert 'cash' in result
    assert 'tolerance' in result
    assert result['tolerance'] == 0.1
    assert result['cash']['percent'] == 0.5
    
    # Verify positions DataFrame
    positions_df = result['positions']
    assert 'conid' in positions_df.columns
    assert 'percent' in positions_df.columns

def test_load_portfolio_targets():
    # Create test data
    portfolio_state = {
        'positions': pd.DataFrame({
            'conid': [1, 2],
            'position': [100, 200],
            'ave_cost': [50, 60]
        }),
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'position': [10000]
        })
    }
    
    portfolio_model = {
        'positions': pd.DataFrame({
            'conid': [1, 2, 3],
            'percent': [0.3, 0.3, 0.2]
        }),
        'cash': {'percent': 0.2},
        'tolerance': 0.05
    }
    
    # Test function
    result = load_portfolio_targets(portfolio_state, portfolio_model)
    
    # Verify results
    assert isinstance(result, dict)
    assert 'positions' in result
    assert 'cash' in result
    assert 'tolerance' in result
    assert result['tolerance'] == 0.05
    
    # Verify positions DataFrame
    positions_df = result['positions']
    assert 'conid' in positions_df.columns
    assert 'position' in positions_df.columns
    assert 'ave_cost' in positions_df.columns
    assert 'percent_target' in positions_df.columns
    assert len(positions_df) == 3  # Should include all positions from both inputs 