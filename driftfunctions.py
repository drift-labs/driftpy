from anchorpy import Idl, Program, Provider
from solana.publickey import PublicKey
import json
import time
import os
from pathlib import Path
from driftpy.clearing_house import ClearingHouse
import asyncio
import sys
from driftpy.constants.markets import MARKETS
from driftpy.constants.numeric_constants import MARK_PRICE_PRECISION
from datetime import datetime, timedelta
import pandas as pd
import math

FUNDING_PRECISION = 1e4
PEG_PRECISION = 10**3
AMM_TO_QUOTE_PRECISION_RATIO = 10**7

CH_PID = "dammHkt7jmytvbS3nHTxQNEcP59aE57nxwV21YdqEDN"
IDL_FILE = os.path.join(os.path.dirname('driftpy.idl.__file__'), 'venv\Lib\site-packages\driftpy\idl\clearing_house.json')

with Path(IDL_FILE).open() as f:
    raw_idl = json.load(f)
idlO = Idl.from_json(raw_idl)

if "ANCHOR_PROVIDER_URL" not in os.environ:
    os.environ["ANCHOR_PROVIDER_URL"] =  "https://api.mainnet-beta.solana.com/"

#os.environ["ANCHOR_WALLET"] =  "PATH_TO_WALLET" # uncomment this line and paste the path to your wallet.json file if solana config wallet file not found
    
# Address of the deployed program.
program_id = PublicKey(CH_PID)
program = Program(idlO, program_id, Provider.env())

""""""

def calculate_market_summary(markets):

    markets_summary = pd.concat([
        pd.DataFrame(MARKETS).iloc[:,:3],
    pd.DataFrame(markets.markets),
    pd.DataFrame([x.amm for x in markets.markets]),           
              ],axis=1).dropna(subset=['symbol'])
    return markets_summary

""""""

def calculate_predicted_funding(markets, markets_summary):

    last_funding_ts = pd.to_datetime(markets.markets[0].amm.last_funding_rate_ts*1e9)
    next_funding_ts = last_funding_ts + timedelta(hours=1)
    next_funding_ts

    summary = {}
    summary['next_funding_rate'] = (markets_summary['last_mark_price_twap'] \
                         - markets_summary['last_oracle_price_twap'])\
    /markets_summary['last_oracle_price_twap']/24
    
    summary['mark_price'] = (markets_summary['quote_asset_reserve'] \
                         /markets_summary['base_asset_reserve'])\
    *markets_summary['peg_multiplier']/1e3

    return pd.concat([pd.DataFrame(MARKETS).iloc[:,:3], pd.DataFrame(summary)],axis=1)

""""""

def calculate_price(base_asset_amount, quote_asset_amount, peg_multiplier):
    if abs(base_asset_amount) <= 0:
        return 0
    else:
        return ((quote_asset_amount*peg_multiplier/PEG_PRECISION)/base_asset_amount)

""""""

def calculate_mark_price(market):
    return calculate_price(market.amm.base_asset_reserve, market.amm.quote_asset_reserve, market.amm.peg_multiplier)

""""""

def calculate_target_price_trade(market, target_price: float, output_asset_type = 'quote'):

    mark_price_before = calculate_mark_price(market)
    
    if target_price > mark_price_before:
        price_gap = target_price - mark_price_before
        target_price = mark_price_before + price_gap
    else:
        price_gap = mark_price_before - target_price
        target_price = mark_price_before - price_gap

    base_asset_reserve_before = market.amm.base_asset_reserve/MARK_PRICE_PRECISION
    quote_asset_reserve_before = market.amm.quote_asset_reserve/MARK_PRICE_PRECISION
    peg = market.amm.peg_multiplier/MARK_PRICE_PRECISION
    invariant = (market.amm.sqrt_k/MARK_PRICE_PRECISION)**2
    k = invariant*MARK_PRICE_PRECISION
    bias_modifier = 1

    if mark_price_before > target_price:
        base_asset_reserve_after = math.sqrt((k/target_price)*(peg/PEG_PRECISION) - bias_modifier) - 1
        quote_asset_reserve_after = (k/MARK_PRICE_PRECISION)/base_asset_reserve_after

        direction = 'SHORT'
        trade_size = ((quote_asset_reserve_before - quote_asset_reserve_after)*(peg/PEG_PRECISION))/AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_after - base_asset_reserve_before

    elif mark_price_before < target_price:
        base_asset_reserve_after = math.sqrt((k/target_price)*(peg/PEG_PRECISION) + bias_modifier) + 1
        quote_asset_reserve_after = (k/MARK_PRICE_PRECISION)/base_asset_reserve_after
        
        direction = 'LONG'
        trade_size = ((quote_asset_reserve_after - quote_asset_reserve_before)*(peg/PEG_PRECISION))/AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_before - base_asset_reserve_after

    else:
        # no trade, market is at target
        direction = 'LONG'
        trade_size = 0
        return [direction, trade_size, target_price, target_price]

    entry_price = trade_size*AMM_TO_QUOTE_PRECISION_RATIO*MARK_PRICE_PRECISION/abs(base_size)

    if output_asset_type == 'quote':
        return [direction, trade_size*MARK_PRICE_PRECISION*FUNDING_PRECISION, entry_price, target_price]
    else:
        return [direction, base_size/PEG_PRECISION, entry_price, target_price]

""""""

def calculate_swap_output(input_asset_reserve, swap_amount, invariant):
    new_input_asset_reserve = input_asset_reserve + swap_amount
    new_output_asset_reserve = invariant/new_input_asset_reserve
    return [new_input_asset_reserve, new_output_asset_reserve]

""""""

def calculate_amm_reserves_after_swap(amm, input_asset_type, swap_amount, swap_direction):
    
    if input_asset_type == 'quote':
        swap_amount = swap_amount*MARK_PRICE_PRECISION*(PEG_PRECISION**2)/(amm.peg_multiplier*MARK_PRICE_PRECISION)
        if swap_direction == 'SHORT':
            swap_amount = swap_amount*(-1)
        [new_quote_asset_reserve, new_base_asset_reserve] = calculate_swap_output(amm.quote_asset_reserve/MARK_PRICE_PRECISION, 
                                                        swap_amount,
                                                        (amm.sqrt_k/MARK_PRICE_PRECISION)**2)

    else:
        swap_amount = swap_amount*PEG_PRECISION
        if swap_direction == 'LONG':
            swap_amount = swap_amount*(-1)
        [new_base_asset_reserve, new_quote_asset_reserve] = calculate_swap_output(amm.base_asset_reserve/MARK_PRICE_PRECISION,
                                                        swap_amount,
                                                        (amm.sqrt_k/MARK_PRICE_PRECISION)**2)
    
    return [new_quote_asset_reserve, new_base_asset_reserve]
    
""""""    

def calculate_trade_acquired_amounts(direction, amount, market, input_asset_type = 'quote'):
    if amount == 0:
        return [0, 0]

    [new_quote_asset_reserve, new_base_asset_reserve] = calculate_amm_reserves_after_swap(market.amm, input_asset_type, amount, direction)

    acquired_base = market.amm.base_asset_reserve/MARK_PRICE_PRECISION - new_base_asset_reserve
    acquired_quote = market.amm.quote_asset_reserve/MARK_PRICE_PRECISION - new_quote_asset_reserve

    return [acquired_base, acquired_quote]

""""""

def calculate_trade_slippage(direction, amount, market, input_asset_type = 'quote'):

    old_price = calculate_mark_price(market)
    if amount == 0:
        return [0, 0, old_price, old_price]

    [acquired_base, acquired_quote] = calculate_trade_acquired_amounts(direction, amount, market, input_asset_type)

    entry_price = calculate_price(acquired_base, acquired_quote, market.amm.peg_multiplier*(-1)/MARK_PRICE_PRECISION)*MARK_PRICE_PRECISION

    new_price = calculate_price(market.amm.base_asset_reserve/MARK_PRICE_PRECISION - acquired_base, 
                            market.amm.quote_asset_reserve/MARK_PRICE_PRECISION - acquired_quote, 
                            market.amm.peg_multiplier/MARK_PRICE_PRECISION)*MARK_PRICE_PRECISION

    if direction == 'SHORT':
        assert new_price < old_price
    else:
        assert old_price < new_price

    pct_max_slippage = abs((new_price - old_price)/old_price)
    pct_avg_slippage = abs((entry_price - old_price)/old_price)

    return [pct_avg_slippage, pct_max_slippage, entry_price, new_price]

async def main():
    #Try out  the functions here
    
    #Initiate ClearingHouse
    drift_acct = await ClearingHouse.create(program)
    drift_user_acct = await drift_acct.get_user_account()

    #Get the total value of your collateral
    balance = (drift_user_acct.collateral/1e6)
    print(f'Total Collateral: {balance}')

    asset = 'SOL' #Select which asset you want to use here

    drift_assets = ['SOL', 'BTC', 'ETH', 'LUNA', 'AVAX', 'BNB', 'MATIC', 'ATOM', 'DOT', 'ALGO']
    idx = drift_assets.index(asset)

    markets = await drift_acct.get_markets_account()
    market = markets.markets[idx]

    markets_summary = calculate_market_summary(markets)

    #Get the predicted funding rates of each market
    print(calculate_predicted_funding(markets, markets_summary))

    #Liquidity required to move AMM price of SOL to 95
    print(calculate_target_price_trade(market, 95, output_asset_type='quote'))

    #Slippage of a $5000 long trade
    print(calculate_trade_slippage('LONG', 5000, market, input_asset_type='quote'))
    
asyncio.run(main())
