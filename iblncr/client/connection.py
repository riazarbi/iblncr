from ib_async.ib import IB

def ib_connect(host: str = "127.0.0.1", port: int = 4003, client_id: int = 1,
              account: str = None):
    """
    Establishes a connection to Interactive Brokers TWS/Gateway.
    
    Args:
        host (str, optional): The hostname or IP address of the TWS/Gateway.
            Defaults to "127.0.0.1".
        port (int, optional): The port number to connect to. Defaults to 4003.
        client_id (int, optional): A unique client identifier. Defaults to 1.
        account (str, optional): The account ID to use. If None, available accounts
            will be listed.
    
    Returns:
        IB: An initialized and connected IB client instance.
        
    Raises:
        ValueError: If account is not specified and multiple accounts are available.
        
    Note:
        - The connection is blocking until established
        - Market data type is set to delayed frozen data (type 3)
    """
    ib = IB()
    
    if account is None:
        ib.connect(host, port, client_id)  # Connect first without account
        managed_accounts = ib.managedAccounts()
        if managed_accounts:
            ib.disconnect()
            raise ValueError(
                "Account ID not specified. Please specify one of the following "
                f"accounts: {managed_accounts}")
    
    # Reconnect with the specified account if we get here
    ib.connect(host, port, client_id, account)
    ib.reqMarketDataType(3)
    return ib


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