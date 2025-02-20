import pytest
from click.testing import CliRunner
from unittest.mock import patch
from iblncr.main import cli

@pytest.fixture
def runner():
    return CliRunner()

@patch('iblncr.main.ib_connect')
def test_cli_shows_help_with_no_args(mock_connect, runner):
    with patch('sys.argv', ['iblncr']):  # Mock sys.argv to be empty
        result = runner.invoke(cli)
        assert result.exit_code == 0
        assert 'Interactive Brokers Portfolio Rebalancer' in result.output
        assert '--account' in result.output
        assert '--model' in result.output
        assert '--port' in result.output
        mock_connect.assert_not_called()

def test_cli_with_missing_account(runner):
    with patch('iblncr.main.ib_connect') as mock_connect:
        mock_connect.side_effect = ValueError("Account ID not specified. Please specify one of the following accounts: ['123', '456']")
        result = runner.invoke(cli, ['--port', '4003'])
        
        assert "Account ID not specified" in result.output
        assert "['123', '456']" in result.output
        mock_connect.assert_called_once_with(port=4003, account=None)

@patch('iblncr.main.run_rebalancer')
def test_cli_successful_run(mock_rebalancer, runner):
    result = runner.invoke(cli, [
        '--account', 'TEST123',
        '--model', 'test_model.yaml',
        '--port', '4003'
    ])
    
    assert result.exit_code == 0
    assert "Starting portfolio rebalancing for account TEST123" in result.output
    mock_rebalancer.assert_called_once_with('TEST123', 'test_model.yaml', port=4003)

@patch('iblncr.main.run_rebalancer')
def test_cli_with_error(mock_rebalancer, runner):
    mock_rebalancer.side_effect = Exception("Test error")
    
    result = runner.invoke(cli, [
        '--account', 'TEST123',
        '--model', 'test_model.yaml'
    ])
    
    assert result.exit_code != 0
    assert "An error occurred: Test error" in result.output

def test_cli_with_default_values(runner):
    with patch('iblncr.main.run_rebalancer') as mock_rebalancer:
        result = runner.invoke(cli, ['--account', 'TEST123'])
        
        assert result.exit_code == 0
        mock_rebalancer.assert_called_once_with(
            'TEST123',
            'iblncr/data/sample_model.yaml',
            port=4003
        )

def test_cli_with_custom_port(runner):
    with patch('iblncr.main.run_rebalancer') as mock_rebalancer:
        result = runner.invoke(cli, [
            '--account', 'TEST123',
            '--port', '4004'
        ])
        
        assert result.exit_code == 0
        mock_rebalancer.assert_called_once_with(
            'TEST123',
            'iblncr/data/sample_model.yaml',
            port=4004
        ) 