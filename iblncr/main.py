import click
from iblncr.client.connection import ib_connect
from iblncr.rebalancer import run_rebalancer

@click.command()
@click.option(
    '--account', 
    help='Account number. If not provided, available accounts will be listed.'
)
@click.option(
    '--model', 
    default='iblncr/data/sample_model.yaml',
    help='Path to model YAML file'
)
def cli(account: str, model: str) -> None:
    """Interactive Brokers Portfolio Rebalancer"""
    
    if account is None:
        try:
            # This will raise ValueError with available accounts
            ib_connect(account=None)
        except ValueError as e:
            print(e)
            return
    
    print(f"Starting portfolio rebalancing for account {account}")
    
    try:
        run_rebalancer(account, model)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == '__main__':
    cli()
        
 
