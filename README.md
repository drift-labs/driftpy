# DriftPy

<div align="center">
    <img src="docs/img/drift.png" width="30%" height="30%">
</div>

DriftPy is the Python client for the [Drift](https://www.drift.trade/) protocol.
It allows you to trade and fetch data from Drift using Python.

**[Read the full SDK documentation here!](https://drift-labs.github.io/v2-teacher/)**

## Installation

```
pip install driftpy
```

Note: requires Python >= 3.10.


## SDK Examples

- `examples/` folder includes more examples of how to use the SDK including how to provide liquidity/become an lp, stake in the insurance fund, etc.


## Note on using QuickNode

If you are using QuickNode free plan, you *must* use `AccountSubscriptionConfig("demo")`, and you can only subscribe to 1 perp market and 1 spot market at a time.

Non-QuickNode free RPCs (including the public mainnet-beta url) can use `cached` as well.

Example setup for `AccountSubscriptionConfig("demo")`: 

```python
    # This example will listen to perp markets 0 & 1 and spot market 0
    # If you are listening to any perp markets, you must listen to spot market 0 or the SDK will break

    perp_markets = [0, 1]
    spot_market_oracle_infos, perp_market_oracle_infos, spot_market_indexes = get_markets_and_oracles(perp_markets = perp_markets)

    oracle_infos = spot_market_oracle_infos + perp_market_oracle_infos

    drift_client = DriftClient(
        connection,
        wallet, 
        "mainnet",             
        perp_market_indexes = perp_markets,
        spot_market_indexes = spot_market_indexes,
        oracle_infos = oracle_infos,
        account_subscription = AccountSubscriptionConfig("demo"),
    )
    await drift_client.subscribe()
```
If you intend to use `AccountSubscriptionConfig("demo)`, you *must* call `get_markets_and_oracles` to get the information you need.

`get_markets_and_oracles` will return all the necessary `OracleInfo`s and `market_indexes` in order to use the SDK.

# Development

## Setting Up Dev Env

`bash setup.sh`


Ensure correct python version (using pyenv is recommended):
```bash
pyenv install 3.10.11
pyenv global 3.10.11
poetry env use $(pyenv which python)
```

Install dependencies:
```bash
poetry install
```

To run tests, first ensure you have set up the RPC url, then run `pytest`:
```bash
export MAINNET_RPC_ENDPOINT="<YOUR_RPC_URL>"
export DEVNET_RPC_ENDPOINT="https://api.devnet.solana.com" # or your own RPC

poetry run pytest -v -s -x tests/ci/*.py
poetry run pytest -v -s tests/math/*.py
```
