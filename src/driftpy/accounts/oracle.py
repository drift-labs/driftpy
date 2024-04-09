import asyncio
from pathlib import Path

from anchorpy import Coder, Idl, Program

import driftpy
from .types import DataAndSlot
from driftpy.constants.numeric_constants import *
from driftpy.types import OracleSource, OraclePriceData, PrelaunchOracle, is_variant

from solders.pubkey import Pubkey
from solders.account import Account
from pythclient.pythaccounts import PythPriceInfo, _ACCOUNT_HEADER_BYTES, EmaType
from solana.rpc.async_api import AsyncClient
import struct

file = Path(str(driftpy.__path__[0]) + "/idl/switchboard.json")
with file.open() as f:
    raw = file.read_text()
IDL = Idl.from_json(raw)
CODER = Coder(IDL)
file = Path(str(driftpy.__path__[0]) + "/idl/drift.json")
with file.open() as f:
    raw = file.read_text()
DRIFT_IDL = Idl.from_json(raw)
DRIFT_CODER = Coder(DRIFT_IDL)


def convert_pyth_price(price, scale=1):
    return int(price * PRICE_PRECISION * scale)


def convert_switchboard_decimal(mantissa: int, scale: int = 1):
    swb_precision = 10**scale
    return int((mantissa * PRICE_PRECISION) // swb_precision)


async def get_oracle_price_data_and_slot(
    connection: AsyncClient, address: Pubkey, oracle_source=OracleSource.Pyth()
) -> DataAndSlot[OraclePriceData]:
    if "Pyth" in str(oracle_source):
        rpc_reponse = await connection.get_account_info(address)
        rpc_response_slot = rpc_reponse.context.slot

        oracle_price_data = decode_pyth_price_info(
            rpc_reponse.value.data, oracle_source
        )

        return DataAndSlot(data=oracle_price_data, slot=rpc_response_slot)
    elif is_variant(oracle_source, "QuoteAsset"):
        return DataAndSlot(
            data=OraclePriceData(PRICE_PRECISION, 0, 1, 1, 0, True), slot=0
        )
    elif is_variant(oracle_source, "Switchboard"):
        rpc_reponse = await connection.get_account_info(address)
        rpc_response_slot = rpc_reponse.context.slot

        oracle_price_data = decode_swb_price_info(rpc_reponse.value.data)

        return DataAndSlot(data=oracle_price_data, slot=rpc_response_slot)
    elif is_variant(oracle_source, "Prelaunch"):
        rpc_reponse = await connection.get_account_info(address)
        rpc_response_slot = rpc_reponse.context.slot

        oracle_price_data = decode_prelaunch_price_info(rpc_reponse.value.data)

        return DataAndSlot(data=oracle_price_data, slot=rpc_response_slot)
    else:
        raise NotImplementedError("Unsupported Oracle Source", str(oracle_source))


def oracle_ai_to_oracle_price_data(
    oracle_ai: Account, oracle_source=OracleSource.Pyth()
) -> DataAndSlot[OraclePriceData]:
    if "Pyth" in str(oracle_source):
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
    oracle_source=OracleSource.Pyth(),
) -> OraclePriceData:
    offset = _ACCOUNT_HEADER_BYTES
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
    )  # exponent decimals from oracle to PRICE_PRECISION of 6

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


def decode_swb_price_info(data: bytes):
    account = CODER.accounts.decode(data)

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


def decode_oracle(oracle_ai: bytes, oracle_source: OracleSource):
    if "Pyth" in str(oracle_source):
        return decode_pyth_price_info(oracle_ai, oracle_source)
    elif "Switchboard" in str(oracle_source):
        return decode_swb_price_info(oracle_ai)
    elif "Prelaunch" in str(oracle_source):
        return decode_prelaunch_price_info(oracle_ai)
    else:
        raise Exception("Unknown oracle source")


def get_oracle_decode_fn(oracle_source: OracleSource):
    if "Pyth" in str(oracle_source):
        return lambda data: decode_pyth_price_info(data, oracle_source)
    elif "Switchboard" in str(oracle_source):
        return lambda data: decode_swb_price_info(data)
    elif "Prelaunch" in str(oracle_source):
        return lambda data: decode_prelaunch_price_info(data)
    else:
        raise Exception("Unknown oracle source")
