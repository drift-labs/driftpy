# DriftPy

<div align="center">
    <img src="https://camo.githubusercontent.com/d41b63c668d34e0ac5baba28a6fcff818da7b168752e511a605096dd9ba94039/68747470733a2f2f75706c6f6164732d73736c2e776562666c6f772e636f6d2f3631313538303033356164353962323034333765623032342f3631366639376134326635363337633435313764303139335f4c6f676f2532302831292532302831292e706e67" width="30%" height="30%">
</div>

DriftPy is the Python client for the [Drift](https://www.drift.trade/) protocol. It allows you to trade and fetch data from Drift using Python.

## Installation

```
pip install driftpy
```

Note: requires Python >= 3.9.

## Development

### Development Setup

If you want to contribute to DriftPy, follow these steps to get set up:

1. Install [poetry](https://python-poetry.org/docs/#installation)
2. Install dev dependencies:
```sh
poetry install

```
3. Install [nox-poetry](https://github.com/cjolowicz/nox-poetry) (note: do not use Poetry to install this, see [here](https://medium.com/@cjolowicz/nox-is-a-part-of-your-global-developer-environment-like-poetry-pre-commit-pyenv-or-pipx-1cdeba9198bd))
4. Activate the poetry shell:
```sh
poetry shell

```

### Testing

1. Run `make test`.
2. Run `make lint`.

### Building the docs

Run `mkdocs serve` to build the docs and serve them locally.
