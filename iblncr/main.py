import time
import pandas as pd
from datetime import datetime
import click
import plotille

from iblncr.client.portfolio import (
    get_portfolio_model,
    get_portfolio_state,
    load_portfolio_targets
)
from iblncr.client.pricing import price_portfolio, solve_portfolio
from iblncr.client.orders import (
    constrain_orders,
    price_orders,
    submit_orders,
    cancel_orders,
    get_filled_orders
)
from iblncr.client.connection import ib_connect

def update_rebalance_history(portfolio_solved, rebalance_history, run):
    """
    Updates the rebalance history DataFrame with current portfolio state.
    
    Args:
        portfolio_solved (dict): Dictionary containing 'positions' and 'cash' DataFrames
        rebalance_history (pd.DataFrame): Existing history DataFrame to append to
        
    Returns:
        pd.DataFrame: Updated rebalance history
    """
    # Create combined history entry
    positions_history = portfolio_solved['positions'][['conid', 'percent_held', 'percent_target']].copy()
    positions_history['type'] = 'position'
    positions_history.rename(columns={'conid': 'identifier'}, inplace=True)

    cash_history = portfolio_solved['cash'][['currency', 'percent_held', 'percent_target']].copy()
    cash_history['type'] = 'cash'
    cash_history.rename(columns={'currency': 'identifier'}, inplace=True)

    current_snapshot = pd.concat([positions_history, cash_history])
    current_snapshot['timestamp'] = datetime.now()
    current_snapshot = current_snapshot.assign(run=run)
    
    return pd.concat([rebalance_history, current_snapshot], ignore_index=True)

def plot_rebalance_history(rebalance_history):
    """
    Creates a text-based line chart of the rebalance history using plotille.
    Shows both percent_held and percent_target over time for each identifier.
    """

    # Plot for each unique identifier
    for identifier in rebalance_history['identifier'].unique():
        fig = plotille.Figure()
        fig.width = 40
        fig.height = 10

        mask = rebalance_history['identifier'] == identifier
        data = rebalance_history[mask]

        fig.set_x_limits(min_=0, max_=1+float(data['run'].max()))
        fig.set_y_limits(min_=0, max_=10+max(float(data['percent_held'].max()),float(data['percent_target'].max())))
        fig.color_mode = 'byte'
        fig.x_label = "Run" 
        fig.y_label = "Portfolio Percentage"
                
        # Plot percent_held (solid line)
        fig.plot(
            data['run'].values.tolist(),
            data['percent_held'].values.tolist(),
            label=f"{identifier} (held)",
            interp='linear'
        )
        
        # Plot percent_target (dotted line)
        fig.plot(
            data['run'].values.tolist(),
            data['percent_target'].values.tolist(),
            label=f"{identifier} (target)",
            interp='linear'
        )
        print(fig.show(legend=True))

@click.command()
@click.option('--account', required=True, help='Account number')
@click.option('--model', required=True, help='Path to model YAML file')
def cli(account: str, model: str):
    """Interactive Brokers Portfolio Rebalancer"""
    print(f"=> Starting portfolio rebalancing for account {account}")
    
    try:
        run = 0
        out_of_band = True
        rebalance_history = pd.DataFrame()  # Initialize empty DataFrame
        
        while out_of_band:
            run += 1
            print(f"=> Loading portfolio model from {model}")
            portfolio_model = get_portfolio_model(model, account=account)
            
            print("=> Fetching current portfolio state")
            portfolio_state = get_portfolio_state(account=account)

            print("=> Calculating portfolio targets")
            portfolio_targets = load_portfolio_targets(portfolio_state, portfolio_model)

            print("=> Pricing portfolio")
            portfolio_priced = price_portfolio(portfolio_targets, account=account)

            print("=> Solving portfolio optimization")
            portfolio_solved = solve_portfolio(portfolio_priced)

            print("\nPortfolio Positions:")
            print(portfolio_solved['positions'])
            print("\nPortfolio Cash:")
            print(portfolio_solved['cash'])
            print("\n")

            rebalance_history = update_rebalance_history(portfolio_solved, rebalance_history, run)
            print(plot_rebalance_history(rebalance_history))


            out_of_band = (
                any(portfolio_solved['cash'].out_of_band) or
                any(portfolio_solved['positions'].out_of_band)
            )

            if out_of_band:
                print("=> Portfolio is out of balance - executing trades")
                print("=> Calculating order constraints")
                order_quantities = constrain_orders(portfolio_solved, account=account)

                print("=> Pricing orders")
                orders = price_orders(order_quantities, account=account)

                print("\nOrders:")
                print(orders)
                print("\n")

                if orders is not None:
                    print("=> Submitting orders")
                    submit_orders(orders, account=account)     
                    print("=> Waiting 30 seconds before canceling unfilled orders")
                    time.sleep(30)

                    print("=> Getting filled orders")
                    filled_orders = get_filled_orders(account=account)
                    print(filled_orders)

                    print("=> Canceling remaining orders")
                    cancel_orders(account=account)
                else:
                    print("=> Failed to price orders.")

            else: 
                print("=> Portfolio weights are within tolerance. Exiting")

    except Exception as e:
        print(f"ERROR: An error occurred: {str(e)}")
        raise

if __name__ == '__main__':
    cli()
        
 
