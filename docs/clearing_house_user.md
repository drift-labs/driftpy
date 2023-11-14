# User

This object is used to fetch data from the protocol and view user metrics (leverage, free collateral, etc.)

## Example

```python
drift_client = DriftClient.from_config(config, provider)
drift_user = User(drift_client)

# inspect user's leverage
leverage = await drift_user.get_leverage()
print('current leverage:', leverage / 10_000)

# you can also inspect other accounts information using the (authority=) flag
bigz_acc = User(drift_client, authority=PublicKey('bigZ'))
leverage = await bigz_acc.get_leverage()
print('bigZs leverage:', leverage / 10_000)

# user calls can be expensive on the rpc so we can cache them
drift_user = User(drift_client, use_cache=True)
await drift_user.set_cache()

# works without any rpc calls (uses the cached data)
upnl = await drift_user.get_unrealized_pnl(with_funding=True)
print('upnl:', upnl)
```

:::driftpy.drift_user
