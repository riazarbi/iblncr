import pytest
import pandas as pd
from unittest.mock import Mock, patch
from datetime import datetime
from iblncr.rebalancer import (
    update_rebalance_history,
    execute_orders,
    perform_rebalance,
    plot_rebalance_progress,
    run_rebalancer
)

@pytest.fixture
def sample_portfolio_solved():
    return {
        'positions': pd.DataFrame({
            'conid': [1, 2],
            'percent_held': [45, 45],
            'percent_target': [40, 40],
            'percent_deviation': [5, 5],
            'out_of_band': [True, True]
        }),
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'percent_held': [10],
            'percent_target': [20],
            'percent_deviation': [10],
            'out_of_band': [True]
        })
    }

@pytest.fixture
def sample_rebalance_history():
    return pd.DataFrame({
        'identifier': ['1', '2', 'USD'],
        'type': ['position', 'position', 'cash'],
        'percent_held': [45, 45, 10],
        'percent_target': [40, 40, 20],
        'percent_deviation': [5, 5, 10],
        'timestamp': [datetime.now()] * 3,
        'run': [1] * 3
    })

def test_update_rebalance_history(sample_portfolio_solved, sample_rebalance_history):
    result = update_rebalance_history(sample_portfolio_solved, sample_rebalance_history, run=2)
    
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 6  # Original 3 rows + 3 new rows
    assert 2 in result['run'].values  # New run number present
    assert all(col in result.columns for col in [
        'identifier', 'type', 'percent_held', 'percent_target',
        'percent_deviation', 'timestamp', 'run'
    ])

@patch('iblncr.rebalancer.submit_orders')
@patch('iblncr.rebalancer.get_filled_orders')
@patch('iblncr.rebalancer.cancel_orders')
@patch('time.sleep')
def test_execute_orders(mock_sleep, mock_cancel, mock_get_filled, mock_submit):
    # Setup
    orders = pd.DataFrame({'test': [1, 2, 3]})
    mock_get_filled.return_value = pd.DataFrame({'filled': [1, 2]})
    
    # Test
    result = execute_orders(orders, account="test_account", port=4003)
    
    # Verify
    mock_submit.assert_called_once_with(orders, account="test_account", port=4003)
    mock_sleep.assert_called_once_with(60)
    mock_get_filled.assert_called_once_with(account="test_account", port=4003)
    mock_cancel.assert_called_once_with(account="test_account", port=4003)
    assert isinstance(result, pd.DataFrame)

def test_execute_orders_none():
    result = execute_orders(None, account="test_account")
    assert result is None

@patch('iblncr.rebalancer.constrain_orders')
@patch('iblncr.rebalancer.price_orders')
@patch('iblncr.rebalancer.execute_orders')
def test_perform_rebalance(mock_execute, mock_price, mock_constrain, sample_portfolio_solved):
    # Setup
    mock_constrain.return_value = pd.DataFrame({'test': [1, 2]})
    mock_price.return_value = pd.DataFrame({'test': [3, 4]})
    mock_execute.return_value = pd.DataFrame({'test': [5, 6]})
    
    # Test
    result = perform_rebalance(sample_portfolio_solved, account="test_account")
    
    # Verify
    mock_constrain.assert_called_once()
    mock_price.assert_called_once()
    mock_execute.assert_called_once()
    assert isinstance(result, pd.DataFrame)

@patch('plotille.Figure')
def test_plot_rebalance_progress(mock_figure, sample_rebalance_history):
    # Test
    plot_rebalance_progress(sample_rebalance_history)
    
    # Verify plotille.Figure was used
    mock_figure.assert_called_once()

@patch('iblncr.rebalancer.get_portfolio_model')
@patch('iblncr.rebalancer.get_portfolio_state')
@patch('iblncr.rebalancer.load_portfolio_targets')
@patch('iblncr.rebalancer.price_portfolio')
@patch('iblncr.rebalancer.solve_portfolio')
@patch('iblncr.rebalancer.perform_rebalance')
def test_run_rebalancer(
    mock_perform_rebalance,
    mock_solve,
    mock_price,
    mock_load_targets,
    mock_get_state,
    mock_get_model,
    sample_portfolio_solved
):
    # Setup - first iteration out of band, second iteration in band
    portfolio_out_of_band = {
        'positions': pd.DataFrame({
            'conid': [1, 2],
            'percent_held': [45, 45],
            'percent_target': [40, 40],
            'percent_deviation': [5, 5],
            'out_of_band': [True, True]
        }),
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'percent_held': [10],
            'percent_target': [20],
            'percent_deviation': [10],
            'out_of_band': [True]
        })
    }
    
    portfolio_in_band = {
        'positions': pd.DataFrame({
            'conid': [1, 2],
            'percent_held': [40, 40],
            'percent_target': [40, 40],
            'percent_deviation': [1, 1],
            'out_of_band': [False, False]
        }),
        'cash': pd.DataFrame({
            'currency': ['USD'],
            'percent_held': [20],
            'percent_target': [20],
            'percent_deviation': [1],
            'out_of_band': [False]
        })
    }
    
    mock_solve.side_effect = [portfolio_out_of_band, portfolio_in_band]
    
    # Test
    run_rebalancer(account="test_account", model="test_model.yaml")
    
    # Verify
    assert mock_get_model.call_count == 2
    assert mock_get_state.call_count == 2
    assert mock_load_targets.call_count == 2
    assert mock_price.call_count == 2
    assert mock_solve.call_count == 2
    assert mock_perform_rebalance.call_count == 1  # Only called when out of band 