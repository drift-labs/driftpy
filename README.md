# DriftPy

<div align="center">
    <img src="https://camo.githubusercontent.com/d41b63c668d34e0ac5baba28a6fcff818da7b168752e511a605096dd9ba94039/68747470733a2f2f75706c6f6164732d73736c2e776562666c6f772e636f6d2f3631313538303033356164353962323034333765623032342f3631366639376134326635363337633435313764303139335f4c6f676f2532302831292532302831292e706e67" width="30%" height="30%">
</div>

DriftPy is the Python client for the [Drift](https://www.drift.trade/) protocol. It allows you to trade and fetch data from Drift using Python.

[Read The Documentation](https://drift-labs.github.io/driftpy/)

## Installation

```
pip install driftpy
```

Note: requires Python >= 3.9.

## Examples

[Arbitrage Trading](https://github.com/0xbigz/driftpy-arb)

[Querying and Visualization](https://gist.github.com/mcclurejt/b244d4ca8b0000ce5078ef8f60e937d9)

## Development

- `git submodule update --init --recursive`
- cd protocol-v2 && yarn 
- cd sdk && yarn && yarn build && cd .. 
- anchor build 
- in deps/serum/dex run `cargo build-bpf`
- update anchor IDL for v2 protocol on new re-builds (copy new idls to src/driftpy/idl/...json)
- run python tests: `bash test.sh v2tests/test.py`

### Development Setup

If you want to contribute to DriftPy, follow these steps to get set up:

1. Install [poetry](https://python-poetry.org/docs/#installation)
2. Install dev dependencies (in local env):
```sh
poetry install
```

### Testing

1. `bash test.sh`

### Building the docs

Run `mkdocs serve` to build the docs and serve them locally.

### Releasing a new version of the package

1. Make sure CHANGELOG.md is updated.
2. Run `bumpversion major|minor|patch` to update the version number locally and create a tagged commit.
3. Run `git push origin <version_number>` to push the tag to GitHub.
4. After merging your PR on GitHub, create a new release at https://github.com/drift-labs/driftpy/releases.
   The CI process will upload a new version of the package to PyPI.
