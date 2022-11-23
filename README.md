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

## SDK Examples

- `examples/` folder includes more examples of how to use the SDK including how to provide liquidity/become an lp, stake in the insurance fund, etc.

## Setting Up Dev Env

`bash setup.sh`

## Running Unit Tests

`bash test.sh`

## Building the docs

Local Docs: `mkdocs serve` 

Updating public docs: `poetry run mkdocs gh-deploy --force`

## Releasing a new version of the package

- `python new_release.py`
- Create a new release at https://github.com/drift-labs/driftpy/releases.
  - (The CI process will upload a new version of the package to PyPI.)