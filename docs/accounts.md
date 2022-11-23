# Accounts

These functions are used to retrieve specific on-chain accounts (State, PerpMarket, SpotMarket, etc.)

## Example 

```python 
clearing_house = ClearingHouse.from_config(config, provider)

# get sol market info 
sol_market_index = 0
sol_market = await get_perp_market_account(clearing_house.program, sol_market_index)
print(
    sol_market.amm.sqrt_k, 
    sol_market.amm.base_asset_amount_long, 
    sol_market.amm.base_asset_amount_short, 
)

# get usdc spot market info
usdc_spot_market_index = 0
usdc_market = await get_spot_market_account(clearing_house.program, usdc_spot_market_index)
print(
    usdc.market_index, 
    usdc.deposit_balance, 
    usdc.borrow_balance, 
)
```

:::driftpy.accounts