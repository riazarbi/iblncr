import pandas as pd
from datetime import datetime
from typing import Dict, Optional
import plotille
import numpy as np

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
    get_filled_orders,
    execute_orders
)

def update_rebalance_history(portfolio_solved, rebalance_history, run):
    """Updates the rebalance history DataFrame with current portfolio state."""
    # Create combined history entry
    positions_history = portfolio_solved['positions'][['conid', 'percent_held', 'percent_target', 'percent_deviation']].copy()
    positions_history['type'] = 'position'
    positions_history.rename(columns={'conid': 'identifier'}, inplace=True)

    cash_history = portfolio_solved['cash'][['currency', 'percent_held', 'percent_target', 'percent_deviation']].copy()
    cash_history['type'] = 'cash'
    cash_history.rename(columns={'currency': 'identifier'}, inplace=True)

    current_snapshot = pd.concat([positions_history, cash_history])
    current_snapshot['timestamp'] = datetime.now()
    current_snapshot = current_snapshot.assign(run=run)
    
    return pd.concat([rebalance_history, current_snapshot], ignore_index=True)



def plot_rebalance_progress(rebalance_history: pd.DataFrame) -> None:
    """Creates a terminal plot showing how positions track towards their targets."""
    # Get unique runs for x-axis
    runs = rebalance_history['run'].unique()
    
    # Replace NA with 0 and Inf with 100 in the percent_deviation column of rebalance_history
    rebalance_history['percent_deviation'] = rebalance_history['percent_deviation'].fillna(0).replace([float('inf'), float('-inf')], 100)
    
    # Initialize plot
    fig = plotille.Figure()
    fig.width = 80
    fig.height = 20
    fig.x_label = "Run" 
    fig.y_label = "Tracking Error %"
    fig.set_x_limits(min_=0, max_=int(max(runs)+1))
    fig.set_y_limits(min_=0, max_=int(rebalance_history['percent_deviation'].max()+5))
    
    # Plot each position/cash difference from target
    for identifier in rebalance_history['identifier'].unique():
        position_data = rebalance_history[rebalance_history['identifier'] == identifier]
        differences = position_data['percent_deviation']
        label = f"{identifier} (deviation: {round(position_data['percent_deviation'].iloc[-1], 2)}%)"
        fig.plot(position_data['run'], differences, label=label, interp='linear')
    
    print("\nTracking error over time (lower is better):")
    print(fig.show(legend=True))
    print("\n")


def run_rebalancer(account: str, model: str, port: int = 4003) -> None:
    """Main rebalancing loop."""
    run = 0
    out_of_band = True
    rebalance_history = pd.DataFrame()

    while out_of_band:
        run += 1
        print(f"Loading portfolio model from {model}")
        portfolio_model = get_portfolio_model(model, account=account, port=port)
        
        print("Fetching current portfolio state")
        portfolio_state = get_portfolio_state(account=account, port=port)

        print("Calculating portfolio targets")
        portfolio_targets = load_portfolio_targets(portfolio_state, portfolio_model)

        print("Pricing portfolio")
        portfolio_priced = price_portfolio(portfolio_targets, account=account, port=port)

        print("Solving portfolio optimization")
        portfolio_solved = solve_portfolio(portfolio_priced)

        print(f"\nPortfolio Positions:\n{portfolio_solved['positions']}")
        print(f"\nPortfolio Cash:\n{portfolio_solved['cash']}")

        rebalance_history = update_rebalance_history(portfolio_solved, rebalance_history, run)

        buy_only = portfolio_model.get('buy_only', False)

        out_of_band = (
            any(portfolio_solved['cash'].out_of_band) or
            any(portfolio_solved['positions'].out_of_band)
        )

        if out_of_band:
            plot_rebalance_progress(rebalance_history)
            print("Portfolio is out of balance - executing trades")
            print("Calculating order constraints")

            # Pass buy_only to constrain_orders
            order_quantities = constrain_orders(portfolio_solved, port=port, account=account, buy_only=buy_only)

            print("Pricing orders")
            orders = price_orders(order_quantities, port=port, account=account)

            print(f"\nOrders:\n{orders}\n")
    
            filled_orders = execute_orders(orders, account=account, port=port)
            print(f"\nFilled Orders:\n{filled_orders}\n")
        else:
            print("Portfolio weights are within tolerance. Exiting") 