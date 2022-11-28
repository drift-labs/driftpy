# Clearing House User

This object is used to fetch data from the protocol and view user metrics (leverage, free collateral, etc.)

## Example 

```python 
clearing_house = ClearingHouse.from_config(config, provider)
clearing_house_user = ClearingHouseUser(clearing_house)

# inspect user's leverage 
leverage = await clearing_house_user.get_leverage()
print('current leverage:', leverage / 10_000)

# you can also inspect other accounts information using the (authority=) flag
bigz_chu = ClearingHouseUser(clearing_house, authority=PublicKey('bigZ'))
leverage = await bigz_chu.get_leverage()
print('bigZs leverage:', leverage / 10_000)

# clearing house user calls can be expensive on the rpc so we can cache them 
clearing_house_user = ClearingHouseUser(clearing_house, use_cache=True)
await clearing_house_user.set_cache()

# works without any rpc calls (uses the cached data)
upnl = await chu.get_unrealized_pnl(with_funding=True)
print('upnl:', upnl)
```


:::driftpy.clearing_house_user