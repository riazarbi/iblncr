import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from iblncr.client.orders import constrain_orders

@pytest.fixture
def sample_portfolio():
    return {
        "positions": pd.DataFrame({
            "conid": [1, 2, 3],
            "optimal_order": [100, -50, 200],
            "optimal_order_value": [10000, -5000, 20000],
            "price": [100, 100, 100]
        })
    }

@pytest.fixture
def mock_volume_data():
    return pd.DataFrame({
        "conid": [1, 2, 3],
        "historical_volume": [10000, 5000, 15000]
    })

@patch('iblncr.client.orders.get_median_daily_volume')
def test_constrain_orders_basic(mock_get_volume, sample_portfolio, mock_volume_data):
    # Setup mock
    mock_get_volume.return_value = mock_volume_data
    
    # Test with default parameters
    result = constrain_orders(sample_portfolio)
    
    # Verify the result is a DataFrame with expected columns
    assert isinstance(result, pd.DataFrame)
    assert all(col in result.columns for col in ['conid', 'order', 'value'])
    
    # Verify volume constraints (2% of historical volume)
    assert all(abs(result['order']) <= mock_volume_data['historical_volume'] * 0.02)

@patch('iblncr.client.orders.get_median_daily_volume')
def test_constrain_orders_buy_only(mock_get_volume, sample_portfolio, mock_volume_data):
    # Setup mock
    mock_get_volume.return_value = mock_volume_data
    
    # Test with buy_only=True
    result = constrain_orders(sample_portfolio, buy_only=True)
    
    # Verify no negative orders (sells)
    assert all(result['order'] >= 0)
    assert all(result['value'] >= 0)

@patch('iblncr.client.orders.get_median_daily_volume')
def test_constrain_orders_size_limits(mock_get_volume, sample_portfolio, mock_volume_data):
    # Setup mock
    mock_get_volume.return_value = mock_volume_data
    
    min_size = 2000
    max_size = 8000
    
    result = constrain_orders(
        sample_portfolio,
        min_order_size=min_size,
        max_order_size=max_size
    )
    
    # Verify order value constraints
    non_zero_values = result['value'][result['value'] != 0]
    assert all(abs(non_zero_values) >= min_size)
    assert all(abs(non_zero_values) <= max_size)

@patch('iblncr.client.orders.get_median_daily_volume')
def test_constrain_orders_volume_limit(mock_get_volume, sample_portfolio, mock_volume_data):
    # Setup mock
    mock_get_volume.return_value = mock_volume_data
    
    vol_limit = 0.01  # 1%
    
    result = constrain_orders(
        sample_portfolio,
        daily_vol_pct_limit=vol_limit
    )
    
    # Verify volume constraints
    for _, row in result.iterrows():
        historical_vol = mock_volume_data[
            mock_volume_data['conid'] == row['conid']
        ]['historical_volume'].iloc[0]
        assert abs(row['order']) <= historical_vol * vol_limit 