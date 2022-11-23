# Clearing House

This object is used to interact with the protocol (deposit, withdraw, trade, lp, etc.)

## Example 

```python 
clearing_house = ClearingHouse.from_config(config, provider)

# open a 10 SOL long position
sig = await clearing_house.open_position(
    PositionDirection.LONG(), # long
    int(10 * BASE_PRECISION), # 10 in base precision
    0, # sol market index
) 

# mint 100 LP shares on the SOL market
await clearing_house.add_liquidity(
    int(100 * AMM_RESERVE_PRECISION), 
    0, 
)
```

:::driftpy.clearing_house