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

**PLEASE**, do not use QuickNode free RPCs to subscribe to the Drift Client.

If you are using QuickNode, you *must* use `AccountSubscriptionConfig("demo")`, and you can only subscribe to 1 perp market and 1 spot market at a time.

Non-QuickNode free RPCs (including the public mainnet-beta url) can use `cached` as well.

Example setup for `AccountSubscriptionConfig("demo")`:

```
    drift_client = DriftClient(
        connection,
        wallet, 
        "mainnet",             
        perp_market_indexes = [0, 1, 2, 3, 4], # indexes of perp markets to listen to
        spot_market_indexes = [0, 1, 2, 3, 4], # indexes of spot markets to listen to
        account_subscription = AccountSubscriptionConfig("demo"),
    )
```

If you don't specify any `market_indexes`, you won't have data from any markets.

**ANYONE** who uses `AccountSubscriptionConfig("demo")` must specify the `market_indexes` that they intend to subscribe to.

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