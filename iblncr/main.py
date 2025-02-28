import click
import sys
from iblncr.client.connection import ib_connect, get_accounts
from iblncr.rebalancer import run_rebalancer
from iblncr.client.orders import cancel_orders
from iblncr.docker_manager import run_docker_container

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def cli():
    """Interactive Brokers Portfolio Rebalancer
    """
    
    # Show help when no arguments are provided
    if len(sys.argv) == 1:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()

@cli.command()
def launch():
    """Launch the IB Gateway Docker container"""
    try:
        run_docker_container()
    except Exception as e:
        click.echo(f"Docker error: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.option(
    '--account', 
    help='Account number. If not provided, available accounts will be listed.'
)

@click.option(
    '--model', 
    required=True,
    help='Path to model YAML file (e.g., iblncr/data/sample_model.yaml)'
)
@click.option(
    '--port',
    default=4003,
    type=int,
    help='Port number for IB Gateway connection (default: 4003)'
)
def rebalance(account: str, model: str, port: int):
    """Run the portfolio rebalancer"""
    # Get available accounts first
    available_accounts = get_accounts(port=port)
    
    if account is None:
        try:
            ib_connect(port=port, account=None)
        except (ValueError, ConnectionRefusedError) as e:
            print(e)
            return
    
    if account not in available_accounts:
        print(f"Error: Account '{account}' not found.")
        print("\nAvailable accounts:")
        for account in available_accounts:
            print(f"  - {account}")
        sys.exit(1)
    
    print(f"Starting portfolio rebalancing for account {account} on port {port}")
    
    try:
        cancel_orders(port = port, account = account)
        run_rebalancer(account, model, port=port)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        sys.exit(1)  # Exit with error code

if __name__ == '__main__':
    cli()
        
 
