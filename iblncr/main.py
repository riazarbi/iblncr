import time
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

def main(account: str):
    print(f"=> Starting portfolio rebalancing for account {account}")
    
    try:
        out_of_band = True
        
        while out_of_band:
            print("=> Loading portfolio model from iblncr/data/sample_model.yaml")
            portfolio_model = get_portfolio_model("iblncr/data/sample_model.yaml", account=account)
            
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

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio rebalancing tool')
    parser.add_argument('account', nargs='?', help='Account identifier to rebalance')
    
    args = parser.parse_args()
    
    if args.account is None:
        try:
            ib = ib_connect()  # This will raise ValueError with account list
        except ValueError as e:
            # The error message already contains the account list
            print(str(e))
    else:
        main(args.account)