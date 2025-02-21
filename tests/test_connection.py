import pytest
from unittest.mock import Mock, patch
from iblncr.client.connection import ib_connect, ib_disconnect, get_ib_server_time, get_accounts
from datetime import datetime

@pytest.fixture
def mock_ib():
    with patch('iblncr.client.connection.IB') as mock_ib_class:
        mock_instance = Mock()
        # Set up the mock instance with a default account
        mock_instance.managedAccounts.return_value = ["test_account"]
        mock_ib_class.return_value = mock_instance
        yield mock_instance

def test_ib_connect_with_account(mock_ib):
    # Test connecting with a specific account
    ib = ib_connect(host="test_host", port=1234, client_id=999, account="test_account")
    
    mock_ib.connect.assert_called_once_with(
        host="test_host", 
        port=1234, 
        clientId=999, 
        account="test_account"
    )
    mock_ib.reqMarketDataType.assert_called_once_with(3)
    assert ib == mock_ib

def test_ib_connect_without_account_raises_error(mock_ib):
    # Test that connecting without an account raises ValueError when accounts exist
    mock_ib.managedAccounts.return_value = ["account1", "account2"]
    
    with pytest.raises(ValueError) as exc_info:
        ib_connect(host="test_host", port=1234, client_id=999)
    
    assert "Account ID not specified" in str(exc_info.value)
    assert "account1" in str(exc_info.value)
    assert "account2" in str(exc_info.value)

def test_ib_disconnect(mock_ib):
    ib_disconnect(mock_ib)
    mock_ib.disconnect.assert_called_once()

def test_get_ib_server_time(mock_ib):
    # Setup mock return value for reqCurrentTime
    expected_time = datetime.now()
    mock_ib.reqCurrentTime.return_value = expected_time
    # Mock no accounts scenario
    mock_ib.managedAccounts.return_value = []
    
    # Test the function
    result = get_ib_server_time(port=1234)
    
    # Verify results
    assert result == expected_time
    # Should be called twice due to the account check
    assert mock_ib.connect.call_count == 2
    mock_ib.disconnect.assert_called()
    mock_ib.reqCurrentTime.assert_called_once()

def test_get_accounts():
    with patch('iblncr.client.connection.IB') as mock_ib:
        # Setup mock IB instance
        mock_instance = mock_ib.return_value
        mock_instance.managedAccounts.return_value = ['account1', 'account2']
        
        accounts = get_accounts()
        
        mock_instance.connect.assert_called_once_with(
            host="127.0.0.1", 
            port=4003, 
            clientId=1
        )
        mock_instance.managedAccounts.assert_called_once()
        mock_instance.disconnect.assert_called_once()
        assert accounts == ['account1', 'account2'] 