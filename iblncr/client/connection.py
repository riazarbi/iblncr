from ib_async.ib import IB

def ib_connect(host: str = "127.0.0.1", port: int = 4003, client_id: int = 1, account: str = None):
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
    ib.connect(host, port, client_id, account)  # Now a blocking call
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