import time
import logging
from iblncr.client.portfolio import (get_portfolio_model, get_portfolio_state, 
                            load_portfolio_targets)
from iblncr.client.pricing import price_portfolio, solve_portfolio
from iblncr.client.orders import constrain_orders, price_orders, submit_orders, cancel_orders

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

def main():
    logger = setup_logging()
    logger.info("Starting portfolio rebalancing")
    
    try:
        logger.info("Loading portfolio model from iblncr/data/sample_model.yaml")
        portfolio_model = get_portfolio_model("iblncr/data/sample_model.yaml")
        
        logger.info("Fetching current portfolio state")
        portfolio_state = get_portfolio_state()
        
        logger.info("Calculating portfolio targets")
        portfolio_targets = load_portfolio_targets(portfolio_state, portfolio_model)

        logger.info("Pricing portfolio")
        portfolio_priced = price_portfolio(portfolio_targets)
        
        logger.info("Solving portfolio optimization")
        portfolio_solved = solve_portfolio(portfolio_priced)

        out_of_band = any([
            any(portfolio_solved['cash'].out_of_band), 
            any(portfolio_solved['positions'].out_of_band)
        ])

        if out_of_band:
            logger.info("Portfolio is out of balance - executing trades")
            logger.info("Calculating order constraints")
            order_quantities = constrain_orders(portfolio_solved)
            
            logger.info("Pricing orders")
            orders = price_orders(order_quantities)
            
            logger.info("Submitting orders")
            submit_orders(orders)
            
            logger.info("Waiting 30 seconds before canceling unfilled orders")
            time.sleep(30)
            
            logger.info("Canceling remaining orders")
            cancel_orders()
        else: 
            logger.info("Portfolio weights are within tolerance. Exiting")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 