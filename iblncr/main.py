import click
import sys
from iblncr.client.connection import ib_connect
from iblncr.rebalancer import run_rebalancer

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option(
    '--account', 
    help='Account number. If not provided, available accounts will be listed.'
)
@click.option(
    '--model', 
    default='iblncr/data/sample_model.yaml',
    help='Path to model YAML file'
)
@click.option(
    '--port',
    default=4003,
    type=int,
    help='Port number for IB Gateway connection (default: 4003)'
)
def cli(account: str, model: str, port: int) -> None:
    """Interactive Brokers Portfolio Rebalancer"""
    # Show help when no arguments are provided
    if len(sys.argv) == 1:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()
    
    if account is None:
        try:
            ib_connect(port=port, account=None)
        except ValueError as e:
            print(e)
            return
    
    print(f"Starting portfolio rebalancing for account {account} on port {port}")
    
    try:
        run_rebalancer(account, model, port=port)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == '__main__':
    cli()
        
 
