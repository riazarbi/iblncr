import time
import logging
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
    cancel_orders
)
from iblncr.client.connection import ib_connect

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

def main(account: str):
    logger = setup_logging()
    logger.info(f"Starting portfolio rebalancing for account {account}")
    
    try:
        logger.info("Loading portfolio model from iblncr/data/sample_model.yaml")
        portfolio_model = get_portfolio_model("iblncr/data/sample_model.yaml", account=account)
        
        logger.info("Fetching current portfolio state")
        portfolio_state = get_portfolio_state(account=account)
        
        logger.info("Calculating portfolio targets")
        portfolio_targets = load_portfolio_targets(portfolio_state, portfolio_model)

        logger.info("Pricing portfolio")
        portfolio_priced = price_portfolio(portfolio_targets, account = account)
        
        logger.info("Solving portfolio optimization")
        portfolio_solved = solve_portfolio(portfolio_priced)

        out_of_band = (
            any(portfolio_solved['cash'].out_of_band) or
            any(portfolio_solved['positions'].out_of_band)
        )

        if out_of_band:
            logger.info("Portfolio is out of balance - executing trades")
            logger.info("Calculating order constraints")
            order_quantities = constrain_orders(portfolio_solved, account = account)
            
            logger.info("Pricing orders")
            orders = price_orders(order_quantities, account = account)
            
            logger.info("Submitting orders")
            submit_orders(orders, account = account)
            
            logger.info("Waiting 30 seconds before canceling unfilled orders")
            time.sleep(30)
            
            logger.info("Canceling remaining orders")
            cancel_orders(account = account)
        else: 
            logger.info("Portfolio weights are within tolerance. Exiting")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
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