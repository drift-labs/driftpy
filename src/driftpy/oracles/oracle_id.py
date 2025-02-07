from solders.pubkey import Pubkey

from driftpy.types import OracleSource, OracleSourceNum


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
    elif "PythLazer1K" in source_str:
        return OracleSourceNum.PYTH_LAZER_1K
    elif "PythLazer1M" in source_str:
        return OracleSourceNum.PYTH_LAZER_1M
    elif "PythLazerStableCoin" in source_str:
        return OracleSourceNum.PYTH_LAZER_STABLE_COIN
    elif "PythLazer" in source_str:
        return OracleSourceNum.PYTH_LAZER
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
    return f"{str(public_key)}-{get_oracle_source_num(source)}"
