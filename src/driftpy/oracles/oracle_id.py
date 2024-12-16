from solders.pubkey import Pubkey

from driftpy.types import OracleSource, OracleSourceNum


def get_num_to_source(num: int) -> OracleSource:
    if num == OracleSourceNum.PYTH:
        return OracleSource.Pyth()  # type: ignore
    elif num == OracleSourceNum.PYTH_1K:
        return OracleSource.Pyth1K()  # type: ignore
    elif num == OracleSourceNum.PYTH_1M:
        return OracleSource.Pyth1M()  # type: ignore
    elif num == OracleSourceNum.PYTH_PULL:
        return OracleSource.PythPull()  # type: ignore
    elif num == OracleSourceNum.PYTH_1K_PULL:
        return OracleSource.Pyth1KPull()  # type: ignore
    elif num == OracleSourceNum.PYTH_1M_PULL:
        return OracleSource.Pyth1MPull()  # type: ignore
    elif num == OracleSourceNum.PYTH_STABLE_COIN_PULL:
        return OracleSource.PythStableCoinPull()  # type: ignore
    elif num == OracleSourceNum.PYTH_STABLE_COIN:
        return OracleSource.PythStableCoin()  # type: ignore
    elif num == OracleSourceNum.PYTH:
        return OracleSource.Pyth()  # type: ignore
    elif num == OracleSourceNum.SWITCHBOARD_ON_DEMAND:
        return OracleSource.SwitchboardOnDemand()  # type: ignore
    elif num == OracleSourceNum.SWITCHBOARD:
        return OracleSource.Switchboard()  # type: ignore
    elif num == OracleSourceNum.QUOTE_ASSET:
        return OracleSource.QuoteAsset()  # type: ignore
    elif num == OracleSourceNum.PRELAUNCH:
        return OracleSource.Prelaunch()  # type: ignore
    else:
        raise ValueError("Unknown oracle source")


def get_oracle_source_num(source: OracleSource) -> int:
    source_str = str(source)

    if "Pyth1M" in source_str:
        return OracleSourceNum.PYTH_1M
    elif "Pyth1K" in source_str:
        return OracleSourceNum.PYTH_1K
    elif "PythPull" in source_str:
        return OracleSourceNum.PYTH_PULL
    elif "Pyth1KPull" in source_str:
        return OracleSourceNum.PYTH_1K_PULL
    elif "Pyth1MPull" in source_str:
        return OracleSourceNum.PYTH_1M_PULL
    elif "PythStableCoinPull" in source_str:
        return OracleSourceNum.PYTH_STABLE_COIN_PULL
    elif "PythStableCoin" in source_str:
        return OracleSourceNum.PYTH_STABLE_COIN
    elif "Pyth" in source_str:
        return OracleSourceNum.PYTH
    elif "SwitchboardOnDemand" in source_str:
        return OracleSourceNum.SWITCHBOARD_ON_DEMAND
    elif "Switchboard" in source_str:
        return OracleSourceNum.SWITCHBOARD
    elif "QuoteAsset" in source_str:
        return OracleSourceNum.QUOTE_ASSET
    elif "Prelaunch" in source_str:
        return OracleSourceNum.PRELAUNCH

    raise ValueError("Invalid oracle source")


def get_oracle_id(public_key: Pubkey, source: OracleSource) -> str:
    """
    Returns the oracle id for a given oracle and source
    """
    if not isinstance(public_key, Pubkey):
        raise ValueError("Invalid public key type")
    return f"{public_key}-{get_oracle_source_num(source)}"
