# DriftPy

<div align="center">
    <img src="docs/img/drift.png" width="30%" height="30%">
</div>

DriftPy is the Python client for the [Drift](https://www.drift.trade/) protocol. It allows you to trade and fetch data from Drift using Python.

**[Read the full SDK documentation here!](https://drift-labs.github.io/driftpy/)**

## Installation

```
pip install driftpy
```

Note: requires Python >= 3.10.

## ⚠️ IMPORTANT ⚠️

If you are using a free RPC URL that is *not* Helius, this pertains to you:

When setting up the Drift Client, you *must* specify which `spot_market_indexes` and `perp_market_indexes` you intend to subscribe to.
In order to avoid a 413 Request Too Large or 429 Too Many Requests, non-Helius free RPCs are limited to listening to up to four of each type of market.

Example setup:

```
    drift_client = DriftClient(
        connection,
        wallet, 
        "mainnet",             
        perp_market_indexes = [0, 1, 2, 3, 4],
        spot_market_indexes = [0, 1, 2, 3, 4],
        account_subscription = AccountSubscriptionConfig("cached"),
    )
```

If you don't specify any `market_indexes`, you won't have data from any markets.
If you specify more than four `market_indexes` *per market type*, your requests will fail with 413 Request Too Large

## SDK Examples

- `examples/` folder includes more examples of how to use the SDK including how to provide liquidity/become an lp, stake in the insurance fund, etc.

## Setting Up Dev Env

`bash setup.sh`


## Building the docs

Local Docs: `mkdocs serve`

Updating public docs: `poetry run mkdocs gh-deploy --force`

## Releasing a new version of the package

- `python new_release.py`
- Create a new release at https://github.com/drift-labs/driftpy/releases.
  - (The CI process will upload a new version of the package to PyPI.)

# Development

Ensure correct python version (using pyenv is recommended):
```
pyenv install 3.10.11
pyenv global 3.10.11
poetry env use $(pyenv which python)
```

Install dependencies:
```
poetry install
```

Run tests:
```
poetry run bash test.sh
```

Run Acceptance Tests
```
poetry run bash acceptance_test.sh
```