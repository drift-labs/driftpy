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

- run `git submodule init` and `git submodule update` to get the protocol-v1 codebase

### Development Setup

If you want to contribute to DriftPy, follow these steps to get set up:

1. Install [poetry](https://python-poetry.org/docs/#installation)
2. Install dev dependencies (in local env):

```sh
poetry install
```

3. Install [nox-poetry](https://github.com/cjolowicz/nox-poetry) (note: do not use Poetry to install this, see [here](https://medium.com/@cjolowicz/nox-is-a-part-of-your-global-developer-environment-like-poetry-pre-commit-pyenv-or-pipx-1cdeba9198bd))


### Testing

1. Run `make test`.
2. Run `make lint`.

### Local Dev
- run `anchor build` in `drift-core/` with `v0.19.0`
- modify `drift-core/program` pubkeys to match `target/deploy/{...}-keypair.json` pubkeys (can use `solana-keygen pubkey {..}.json` view pubkeys) -- for example, for `programs/clearing_house/src/lib.rs`:
```
// #[cfg(feature = "mainnet-beta")]
// declare_id!("...");
// #[cfg(not(feature = "mainnet-beta"))]
declare_id!("{...}"); // use `solana-keygen pubkey target/deploy/clearing_house-keypair.json` here 
```
- also change clearing-house address in `drift-core/Anchor.toml` with the same value

```
[programs.localnet]
clearing_house = "{...}"
```
- re-build: `anchor build`

### Local Dev: Clean Up

- when running tests, you need to kill the validator after each test run
- you can shutdown the validator by finding its PID with `ps aux | grep solana` and sending a kill command, `kill {PID}`

- example with fish shell below: 
```
pytest -v; bash -c $(kill $(ps aux | grep solana | string split ' ' --no-empty | awk "NR==2"))
```

### Building the docs

Run `mkdocs serve` to build the docs and serve them locally.

### Updating the embedded IDLs

DriftPy ships with IDL files for the user's convenience. These live at `src/driftpy/idl` if you need to update them.

### Releasing a new version of the package

1. Make sure CHANGELOG.md is updated.
2. Run `bumpversion major|minor|patch` to update the version number locally and create a tagged commit.
3. Run `git push origin <version_number>` to push the tag to GitHub.
4. After merging your PR on GitHub, create a new release at https://github.com/drift-labs/driftpy/releases.
   The CI process will upload a new version of the package to PyPI.

### Updating the `drift-core` subtree

- This repo pulls in the main Drift repo using [git subtree](https://www.atlassian.com/git/tutorials/git-subtree).
  Follow that linked tutorial if you want to see how it was done.

The short answer:
`git subtree pull --prefix drift-core drift-protocol mainnet-beta --squash`
