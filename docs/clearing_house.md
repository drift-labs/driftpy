# Drift Client

This object is used to interact with the protocol (deposit, withdraw, trade, lp, etc.)

## Example

```python
drift_client = DriftClient.from_config(config,provider)
# open a 10 SOL long position
sig = await drift_client.open_position(
    PositionDirection.LONG(), # long
    int(10 * BASE_PRECISION), # 10 in base precision
    0, # sol market index
)

# mint 100 LP shares on the SOL market
await drift_client.add_liquidity(
    int(100 * AMM_RESERVE_PRECISION),
    0,
)
```

## Configuration

Use the `JUPITER_URL` environment variable to set the endpoint URL for the Jupiter V6 Swap API. This allows you to switch between self-hosted, paid-hosted, or other public API endpoints such as jupiterapi.com for improved rate limits and reduced latency. For more details, see the official [self-hosted](https://station.jup.ag/docs/apis/self-hosted) and [paid-hosted](https://station.jup.ag/docs/apis/self-hosted#paid-hosted-apis) documentation.

:::driftpy.drift_client
