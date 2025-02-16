from ib_async.ib import IB, LimitOrder
from ib_async import Stock
from ib_async import util
import pandas as pd
import numpy as np
from pprint import pprint
import yaml
import time

def ib_connect(host: str = "127.0.0.1", port: int = 4003, client_id: int = 1):
    ib = IB()
    ib.connect("127.0.0.1", 4003, 1)  # Now a blocking call
    ib.reqMarketDataType(3)
    return(ib)


def ib_disconnect(ib):
    ib.disconnect()


def get_ib_server_time():
    ib = ib_connect()
    time_str = ib.reqCurrentTime()
    ib_disconnect(ib)
    return time_str


def get_cash(account):
    if account is None:
        raise ValueError("account argument should not be None")
    ib = ib_connect()
    cash = [x.value for x in ib.accountValues(account = account) if x.tag == "CashBalance" and x.currency == "USD"][0]
    ib_disconnect(ib)
    data = [{"currency": "USD", "position": cash}]
    df = pd.DataFrame(data)
    df["position"] = pd.to_numeric(df["position"])    
    return df


def get_positions(account):
    if account is None:
        raise ValueError("account argument should not be None")
    ib = ib_connect()
    positions = ib.positions(account = account)
    ib_disconnect(ib)
    df = pd.DataFrame([
        {
            "conid": t.contract.conId,
            "position": t.position,
            "ave_cost": t.avgCost
        }
        for t in positions
    ])    
    return df


def get_portfolio_state(account):
    portfolio = {"cash": get_cash(account = account), "positions": get_positions(account = account)}
    return(portfolio)


def get_portfolio_model(path):
    with open(path, "r") as file:
        portfolio_model = yaml.safe_load(file)  # Use safe_load to avoid security risks

    df = pd.DataFrame(portfolio_model["positions"])
    df['contract'] = df.apply(lambda row: Stock(row.symbol, row.exchange, row.currency), axis=1)    
    ib = ib_connect()
    df['contract'] = ib.qualifyContracts(*df['contract'])
    ib_disconnect(ib)
    df['conid'] = df.apply(lambda row: row.contract.conId, axis=1)
    df = df.drop(['contract', 'symbol', 'exchange', 'currency'], axis=1)
    portfolio_model['positions'] = df
    return(portfolio_model) 
    

def load_portfolio_targets(portfolio_state, portfolio_model):
    state = portfolio_state['positions']
    model = portfolio_model['positions']
        
    targets = pd.merge(state, model, how = 'outer', on=['conid'])
    targets = targets.fillna(0)
    targets = targets.rename(columns={"percent": "percent_target"})

    cash = portfolio_state['cash']
    cash['percent_target'] = portfolio_model['cash']['percent']
    tolerance = portfolio_model['tolerance']

    portfolio_targets = {"cash": cash, "positions": targets, "tolerance": tolerance}
    return(portfolio_targets)


def get_quotes(conids):
    ib = ib_connect()
    contracts = [Stock(conId=i) for i in conids]
    all = ib.qualifyContracts(*contracts)    
    tickers = [ib.reqTickers(*all)]
    ib_disconnect(ib)
    df = pd.DataFrame([
        {
            "conid": t.contract.conId,
            "quote_time": t.time,
            "bid_price": t.bid,
            "bid_size": t.bidSize,
            "ask_price": t.ask,
            "ask_size": t.askSize,
            "last": t.last,
            "close": t.close,
            "volume": t.volume,
            "contract": t.contract
        }
        for sublist in tickers for t in sublist  # Flatten the list
    ])    
    return df


def get_median_daily_volume(conids, days = 10):
    ib = ib_connect()
    contracts = [Stock(conId=i) for i in conids]
    all = ib.qualifyContracts(*contracts)    
    average_volume = []

    for al in all:
        bars = ib.reqHistoricalData(
            al,
            endDateTime='',
            durationStr=f'{days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True
        )
    
        # Sum the volume for the 10-day period
        med_vol = np.median([bar.volume for bar in bars])
    
        average_volume.append({"conId": al.conId, "volume": med_vol})

    ib_disconnect(ib)
    df = pd.DataFrame(average_volume)
    return df
  

def price_portfolio(portfolio_targets):
    # Positions
    conids = portfolio_targets["positions"]["conid"].tolist()
    prices = get_quotes(conids)    
    assets = pd.merge(portfolio_targets['positions'],prices, on='conid', how='left')
    assets['price'] = assets.close
    assets['value_held'] = assets.position * assets.price
    
    # Cash
    cash = portfolio_targets['cash']
    cash['price'] = 1
    cash['value_held'] = cash.position * cash.price

    # Math
    total_value  = cash.value_held + sum(assets.value_held)
    assets['percent_held'] = assets.value_held.div(total_value[0]).mul(100).round(2)
    cash['percent_held'] = cash.value_held.div(total_value[0]).mul(100).round(2)
    
    # Keep only relevant columns for downstream processing
    assets = assets[['conid', 'position', 'percent_target', 'price', 'value_held', 'percent_held']]
    
    # Build
    portfolio = {"cash": cash, "positions": assets, "tolerance": portfolio_targets["tolerance"]}
    return(portfolio)


def solve_portfolio(portfolio_priced):
        
    cash = portfolio_priced['cash']
    positions = portfolio_priced['positions']
    total_value  = cash.value_held + sum(positions.value_held)


    cash['value_target'] = cash.percent_target.div(100).mul(total_value[0])
    positions['value_target'] = positions.percent_target.div(100).mul(total_value[0])

    positions['position_target'] = np.floor(positions.value_target / positions.price)
    cash['position_target'] = np.floor(cash.value_target / cash.price)

    positions['percent_deviation'] = abs((positions.value_held - positions.value_target) / positions.value_target) * 100
    cash['percent_deviation'] = abs((cash.value_held - cash.value_target) / cash.value_target) * 100

    positions['out_of_band'] = positions["percent_deviation"].gt(portfolio_priced["tolerance"]['percent'])
    cash['out_of_band'] = cash["percent_deviation"].gt(portfolio_priced["tolerance"]['percent'])

    positions['optimal_order'] = positions.position_target - positions.position
    positions['optimal_value'] = (positions.position + positions.optimal_order) * positions.price
    positions['optimal_order_value'] = positions.price * positions.optimal_order

    post_rebalancing_cash_balance = total_value - sum(positions.optimal_value)
    cash['optimal_value'] = post_rebalancing_cash_balance

    positions = positions[['conid', 'percent_held', 'percent_target', 'position', 'position_target', 'percent_deviation', 'price', 'optimal_order', 'optimal_order_value', 'out_of_band']]

    portfolio_priced['cash'] = cash
    portfolio_priced['positions'] = positions

    return(portfolio_priced)
    

def get_median_daily_volume(conids, days = 10):
    ib = ib_connect()
    contracts = [Stock(conId=i) for i in conids]
    all = ib.qualifyContracts(*contracts)    
    average_volume = []

    for al in all:
        bars = ib.reqHistoricalData(
            al,
            endDateTime='',
            durationStr=f'{days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True
        )
    
        # Sum the volume for the 10-day period
        med_vol = np.median([bar.volume for bar in bars])
    
        average_volume.append({"conid": al.conId, "historical_volume": med_vol})

    ib_disconnect(ib)
    df = pd.DataFrame(average_volume)
    return df
    

def constrain_orders(portfolio_solved,
                    daily_vol_pct_limit = 0.02,
                    min_order_size = 1000,
                    max_order_size = 10000,
                    buy_only = False):


    # extract assets and symbols
    positions = portfolio_solved['positions']

    # Append median historical volumes
    conids = portfolio_targets["positions"]["conid"].tolist()
    volumes = get_median_daily_volume(conids, days = 10)
    positions = pd.merge(positions, volumes, on='conid', how='left')


    # work out the per-symbol constraints
    positions['volume_constraint'] = np.floor(positions.historical_volume.mul(daily_vol_pct_limit))
    positions['max_value_constraint'] = max_order_size
    positions['min_value_constraint'] = min_order_size

    # work out the constrained trade value
    positions['value'] = np.minimum(abs(positions.optimal_order_value), positions.max_value_constraint)
    positions['value'] = positions['value'].where(positions['value'] > positions['min_value_constraint'], 0)
    # work out constrained order size
    positions['order'] = np.floor(np.minimum(positions.volume_constraint, positions.value / positions.price))

    # recompute the constrained value for rounding issues
    positions.value = positions.order * positions.price

    # correct the sign for sell orders
    positions.value = np.where(positions['optimal_order_value'] < 0, -positions['value'], positions['value'])
    positions.order = np.where(positions['optimal_order'] < 0, -positions['order'], positions['order'])

  # drop sells if buy only constraint
    if buy_only:
        # Apply the conditions to 'order' and 'value' columns
        positions['order'] = np.where(positions['order'] < 0, 0, positions['order'])
        positions['value'] = np.where(positions['value'] < 0, 0, positions['value'])
    
    positions = positions[(positions["order"] != 0) | (positions["value"] != 0)]
    
    orders = positions[['conid', 'order', 'value']]
    return(orders)



portfolio_model = get_portfolio_model("iblncr/data/sample_model.yaml")
portfolio_state = get_portfolio_state(account = 'DU1144545')
portfolio_state['positions']
portfolio_targets = load_portfolio_targets(portfolio_state, portfolio_model)
portfolio_targets['positions']

portfolio_priced = price_portfolio(portfolio_targets)
portfolio_priced['cash']
portfolio_priced['positions']

portfolio_solved = solve_portfolio(portfolio_priced)
portfolio_solved['cash']
portfolio_solved['positions']
order_quantities = constrain_orders(portfolio_solved)
orders = price_orders(order_quantities)
orders
submit_orders(orders)
time.sleep(30)
cancel_orders()



def price_orders(order_quantities,
                 spread_tolerance = 0.02):
    
    quotes = get_quotes(order_quantities.conid.tolist())

    quotes = quotes[~quotes[['bid_price', 'ask_price', 'bid_size', 'ask_size']].isin([-1, 0]).any(axis=1)]
    # Drop rows where any of the specified columns are NA (if needed)
    quotes = quotes.dropna(subset=['bid_price', 'ask_price', 'bid_size', 'ask_size'])

    # Check if DataFrame is not empty, calculate spread and filter based on condition
    if len(quotes) > 0:
        quotes['spread'] = (quotes['ask_price'] - quotes['bid_price']) / quotes['ask_price']
        quotes = quotes[quotes['spread'] < spread_tolerance]

    # Check if quotes DataFrame is not empty
    if len(quotes) > 0:
        quotes['limit'] = (quotes['ask_price'] + quotes['bid_price']) / 2
        quotes = quotes[['conid', 'limit']]  # Select only 'symbol' and 'limit'
    else:
        quotes = order_quantities[['conid']]  # Select only 'symbol'
        quotes['limit'] = np.nan  # Add 'limit' column with NA (NaN)

    orders = pd.merge(order_quantities, quotes, on='conid', how='left')
    orders.limit = round(orders.limit, 2)
    orders['value'] = orders.order * orders.limit
    
    return(orders)


def submit_orders(orders):
    ib = ib_connect()
    contracts = [Stock(conId=i) for i in orders.conid.tolist()]
    all = ib.qualifyContracts(*contracts)    
    orders['contract'] = all

    orders['ib_order'] = orders.apply(lambda row: LimitOrder('SELL' if row['value'] < 0 else 'BUY', 
                                              abs(row['order']), row['limit']), axis=1)

    submissions = []
    for _, row in orders.iterrows():
        contract = row['contract']
        order = row['ib_order']
        trade = ib.placeOrder(contract, order)
        submissions.append(trade)
        
    ib_disconnect(ib)


def get_orders():
    ib = ib_connect()
    orders = ib.orders()
    ib_disconnect(ib)
    return orders


def cancel_orders():
    ib = ib_connect()
    ib.reqGlobalCancel()
    ib_disconnect(ib)















pprint(price_portfolio(portfolio_state))


amd = Stock('AMD', 'SMART', 'USD')
intc = Stock('INTC', 'SMART', 'USD')
brk = Stock('BRK B', 'SMART', 'USD')
stocks = [amd, intc, brk]
get_quotes(stocks)
get_cash()
get_positions()


portfolio_state["positions"]["contract"].tolist()


matches = ib.reqMatchingSymbols('intc')
matchContracts = [m.contract for m in matches]
util.df(matchContracts)
assert intc in matchContracts


if __name__ == "__main__":
    time = get_ib_server_time()    
    open_orders = get_orders()
    cash = get_cash()
    orders = get_orders()
    print(get_orders())