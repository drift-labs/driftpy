import struct
from pathlib import Path
from typing import Optional

from anchorpy.coder.coder import Coder
from anchorpy_core.idl import Idl
from pythclient.pythaccounts import ACCOUNT_HEADER_BYTES, EmaType, PythPriceInfo
from solana.rpc.async_api import AsyncClient
from solders.account import Account
from solders.pubkey import Pubkey

import driftpy
from driftpy.constants.numeric_constants import (
    PRICE_PRECISION,
    QUOTE_PRECISION,
    SWB_PRECISION,
)
from driftpy.decode.pull_oracle import decode_pull_oracle
from driftpy.types import OraclePriceData, OracleSource, is_variant

from .types import DataAndSlot

file = Path(str(driftpy.__path__[0]) + "/idl/switchboard.json")
with file.open() as f:
    raw = file.read_text()
IDL = Idl.from_json(raw)
SWB_CODER = Coder(IDL)
file = Path(str(driftpy.__path__[0]) + "/idl/drift.json")
with file.open() as f:
    raw = file.read_text()
DRIFT_IDL = Idl.from_json(raw)
DRIFT_CODER = Coder(DRIFT_IDL)
file = Path(str(driftpy.__path__[0]) + "/idl/switchboard_on_demand.json")
with file.open() as f:
    raw = file.read_text()
SWB_ON_DEMAND_IDL = Idl.from_json(raw)
SWB_ON_DEMAND_CODER = Coder(SWB_ON_DEMAND_IDL)


def convert_pyth_price(price, scale=1):
    return int(price * PRICE_PRECISION * scale)


def convert_switchboard_decimal(mantissa: int, scale: int = 1):
    swb_precision = 10**scale
    return int((mantissa * PRICE_PRECISION) // swb_precision)


def is_pyth_pull_oracle(oracle_source: OracleSource):
    return (
        is_variant(oracle_source, "PythPull")
        or is_variant(oracle_source, "Pyth1KPull")
        or is_variant(oracle_source, "Pyth1MPull")
        or is_variant(oracle_source, "PythStableCoinPull")
    )


def is_pyth_legacy_oracle(oracle_source: OracleSource):
    return (
        is_variant(oracle_source, "Pyth")
        or is_variant(oracle_source, "Pyth1K")
        or is_variant(oracle_source, "Pyth1M")
        or is_variant(oracle_source, "PythStableCoin")
    )


async def get_oracle_price_data_and_slot(
    connection: AsyncClient,
    address: Pubkey,
    oracle_source=OracleSource.Pyth(),  # type: ignore
) -> DataAndSlot[OraclePriceData]:
    if is_variant(oracle_source, "QuoteAsset"):
        return DataAndSlot(
            data=OraclePriceData(PRICE_PRECISION, 0, 1, 1, 0, True), slot=0
        )

    resp = await connection.get_account_info(address)
    slot = resp.context.slot
    if resp.value is None:
        raise ValueError(f"Oracle account not found: {address}")

    oracle_raw = resp.value.data

    data_and_slot: Optional[DataAndSlot[OraclePriceData]] = None
    if is_pyth_pull_oracle(oracle_source):
        oracle_price_data = decode_pyth_pull_price_info(oracle_raw, oracle_source)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_pyth_legacy_oracle(oracle_source):
        oracle_price_data = decode_pyth_price_info(oracle_raw, oracle_source)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "SwitchboardOnDemand"):
        oracle_price_data = decode_swb_on_demand_price_info(oracle_raw)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "Switchboard"):
        oracle_price_data = decode_swb_price_info(oracle_raw)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "Prelaunch"):
        oracle_price_data = decode_prelaunch_price_info(oracle_raw)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "PythLazer"):
        oracle_price_data = decode_pyth_lazer_price_info(oracle_raw)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "PythLazer1K"):
        oracle_price_data = decode_pyth_lazer_price_info(oracle_raw, multiple=1000)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "PythLazer1M"):
        oracle_price_data = decode_pyth_lazer_price_info(oracle_raw, multiple=1000000)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)
    elif is_variant(oracle_source, "PythLazerStableCoin"):
        oracle_price_data = decode_pyth_lazer_price_info(oracle_raw, stable_coin=True)
        data_and_slot = DataAndSlot(data=oracle_price_data, slot=slot)

    if data_and_slot:
        return data_and_slot

    raise NotImplementedError(
        f"Received unexpected oracle source: {str(oracle_source)}"
    )


def oracle_ai_to_oracle_price_data(
    oracle_ai: Account,
    oracle_source=OracleSource.Pyth(),  # type: ignore
) -> DataAndSlot[OraclePriceData]:
    if is_pyth_legacy_oracle(oracle_source):
        oracle_price_data = decode_pyth_price_info(oracle_ai.data, oracle_source)

        return DataAndSlot(oracle_price_data.slot, oracle_price_data)
    elif is_variant(oracle_source, "QuoteAsset"):
        return DataAndSlot(
            data=OraclePriceData(PRICE_PRECISION, 0, 1, 1, 0, True), slot=0
        )
    else:
        raise NotImplementedError("Unsupported Oracle Source", str(oracle_source))


def decode_pyth_price_info(
    buffer: bytes,
    oracle_source=OracleSource.Pyth(),  # type: ignore
) -> OraclePriceData:
    if is_pyth_pull_oracle(oracle_source):
        raise ValueError("Use decode_pyth_pull_price_info for Pyth Pull Oracles")

    offset = ACCOUNT_HEADER_BYTES
    _, exponent, _ = struct.unpack_from("<IiI", buffer, offset)

    # struct.calcsize("IiII") (last I is the number of quoters that make up
    # the aggregate)
    offset += 16
    last_slot, valid_slot = struct.unpack_from("<QQ", buffer, offset)
    offset += 16  # struct.calcsize("QQ")
    derivations = list(struct.unpack_from("<6q", buffer, offset))
    derivations = dict(
        (type_, derivations[type_.value - 1])
        for type_ in [EmaType.EMA_CONFIDENCE_VALUE, EmaType.EMA_PRICE_VALUE]
    )

    twap = derivations[EmaType.EMA_PRICE_VALUE] * (10**exponent)
    twac = derivations[EmaType.EMA_CONFIDENCE_VALUE] * (10**exponent)

    offset += 160

    pyth_price_info = PythPriceInfo.deserialise(buffer, offset, exponent=exponent)

    raw_price_scaler = abs(exponent) - 6

    raw_price_to_price_precision = pyth_price_info.raw_price / (
        10**raw_price_scaler
    )  # exponent decimals from oracle to PRICE_PRECISION 1e6

    scale = 1
    if "1K" in str(oracle_source):
        raw_price_to_price_precision *= 1e3
    elif "1M" in str(oracle_source):
        raw_price_to_price_precision *= 1e6

    return OraclePriceData(
        price=int(raw_price_to_price_precision),
        slot=pyth_price_info.pub_slot,
        confidence=convert_pyth_price(pyth_price_info.confidence_interval, scale),
        twap=convert_pyth_price(twap, scale),
        twap_confidence=convert_pyth_price(twac, scale),
        has_sufficient_number_of_data_points=True,
    )


def decode_swb_on_demand_price_info(data: bytes):
    account = SWB_ON_DEMAND_CODER.accounts.decode(data)

    oracle_raw = account.result

    price = oracle_raw.value // SWB_PRECISION
    slot = oracle_raw.slot
    conf = oracle_raw.range // SWB_PRECISION

    return OraclePriceData(
        price=int(price),
        slot=slot,
        confidence=int(conf),
        twap=None,
        twap_confidence=None,
        has_sufficient_number_of_data_points=True,
    )


def decode_swb_price_info(data: bytes):
    account = SWB_CODER.accounts.decode(data)

    round = account.latest_confirmed_round

    price = convert_switchboard_decimal(round.result.mantissa, round.result.scale)

    conf = max(
        convert_switchboard_decimal(
            round.std_deviation.mantissa, round.std_deviation.scale
        ),
        (price // 1_000),
    )

    has_sufficient_number_of_data_points = (
        round.num_success >= account.min_oracle_results
    )

    slot = round.round_open_slot

    return OraclePriceData(
        price, slot, conf, None, None, has_sufficient_number_of_data_points
    )


def decode_prelaunch_price_info(data: bytes):
    prelaunch_oracle = DRIFT_CODER.accounts.decode(data)

    return OraclePriceData(
        price=prelaunch_oracle.price,
        slot=prelaunch_oracle.amm_last_update_slot,
        confidence=prelaunch_oracle.confidence,
        has_sufficient_number_of_data_points=True,
        twap=None,
        twap_confidence=None,
    )


def decode_pyth_pull_price_info(
    data: bytes, oracle_source: OracleSource = OracleSource.PythPull()
):
    price_update = decode_pull_oracle(data)

    raw_price_scaler = abs(price_update.price_message.exponent) - 6

    raw_price_to_price_precision = price_update.price_message.price / (
        10**raw_price_scaler
    )  # exponent decimals from oracle to PRICE_PRECISION 1e6

    if "1K" in str(oracle_source):
        raw_price_to_price_precision *= 1e3
    elif "1M" in str(oracle_source):
        raw_price_to_price_precision *= 1e6

    return OraclePriceData(
        price=int(raw_price_to_price_precision),
        slot=price_update.posted_slot,
        confidence=price_update.price_message.conf,
        twap=price_update.price_message.ema_price,
        twap_confidence=price_update.price_message.ema_conf,
        has_sufficient_number_of_data_points=True,
    )


def decode_pyth_lazer_price_info(
    data: bytes,
    multiple: int = 1,
    stable_coin: bool = False,
):
    oracle = DRIFT_CODER.accounts.decode(data)

    exponent = abs(oracle.exponent)
    pyth_precision = 10**exponent

    price = convert_pyth_price(oracle.price / pyth_precision, multiple)
    confidence = convert_pyth_price(oracle.conf / pyth_precision, multiple)

    if stable_coin:
        # Stable coin price adjustment logic
        five_bps = 500
        if abs(price - QUOTE_PRECISION) < min(confidence, five_bps):
            price = QUOTE_PRECISION

    price_data = OraclePriceData(
        price=int(price),
        slot=oracle.posted_slot,
        confidence=int(confidence),
        twap=convert_pyth_price(oracle.price / pyth_precision, multiple),
        twap_confidence=convert_pyth_price(oracle.price / pyth_precision, multiple),
        has_sufficient_number_of_data_points=True,
    )
    return price_data


def decode_oracle(oracle_ai: bytes, oracle_source: OracleSource):
    if is_pyth_pull_oracle(oracle_source):
        return decode_pyth_pull_price_info(oracle_ai, oracle_source)
    elif is_pyth_legacy_oracle(oracle_source):
        return decode_pyth_price_info(oracle_ai, oracle_source)
    elif is_variant(oracle_source, "SwitchboardOnDemand"):
        return decode_swb_on_demand_price_info(oracle_ai)
    elif is_variant(oracle_source, "Switchboard"):
        return decode_swb_price_info(oracle_ai)
    elif is_variant(oracle_source, "Prelaunch"):
        return decode_prelaunch_price_info(oracle_ai)
    elif is_variant(oracle_source, "PythLazer"):
        return decode_pyth_lazer_price_info(oracle_ai)
    elif is_variant(oracle_source, "PythLazer1K"):
        return decode_pyth_lazer_price_info(oracle_ai, multiple=1000)
    elif is_variant(oracle_source, "PythLazer1M"):
        return decode_pyth_lazer_price_info(oracle_ai, multiple=1000000)
    elif is_variant(oracle_source, "PythLazerStableCoin"):
        return decode_pyth_lazer_price_info(oracle_ai, stable_coin=True)
    else:
        raise NotImplementedError(
            f"Received unexpected oracle source: {str(oracle_source)}"
        )


def get_oracle_decode_fn(oracle_source: OracleSource):
    if is_pyth_pull_oracle(oracle_source):
        return lambda data: decode_pyth_pull_price_info(data, oracle_source)
    if is_pyth_legacy_oracle(oracle_source):
        return lambda data: decode_pyth_price_info(data, oracle_source)
    elif is_variant(oracle_source, "SwitchboardOnDemand"):
        return lambda data: decode_swb_on_demand_price_info(data)
    elif is_variant(oracle_source, "Switchboard"):
        return lambda data: decode_swb_price_info(data)
    elif is_variant(oracle_source, "Prelaunch"):
        return lambda data: decode_prelaunch_price_info(data)
    elif is_variant(oracle_source, "PythLazer"):
        return lambda data: decode_pyth_lazer_price_info(data)
    elif is_variant(oracle_source, "PythLazer1K"):
        return lambda data: decode_pyth_lazer_price_info(data, multiple=1000)
    elif is_variant(oracle_source, "PythLazer1M"):
        return lambda data: decode_pyth_lazer_price_info(data, multiple=1000000)
    elif is_variant(oracle_source, "PythLazerStableCoin"):
        return lambda data: decode_pyth_lazer_price_info(data, stable_coin=True)
    else:
        raise NotImplementedError(
            f"Received unexpected oracle source: {str(oracle_source)}"
        )
