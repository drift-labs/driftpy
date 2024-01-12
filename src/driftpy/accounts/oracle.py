from dataclasses import dataclass

from .types import DataAndSlot
from driftpy.constants.numeric_constants import *
from driftpy.types import OracleSource, OraclePriceData, is_variant

from solders.pubkey import Pubkey
from solders.account import Account
from pythclient.pythaccounts import PythPriceInfo, _ACCOUNT_HEADER_BYTES, EmaType
from solana.rpc.async_api import AsyncClient
import struct


def convert_pyth_price(price, scale=1):
    return int(price * PRICE_PRECISION * scale)


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

    raw_price_to_price_precision = pyth_price_info.raw_price // (
        10**raw_price_scaler
    )  # exponent decimals from oracle to PRICE_PRECISION of 6

    scale = 1
    if "1K" in str(oracle_source):
        raw_price_to_price_precision *= 1e3
    elif "1M" in str(oracle_source):
        raw_price_to_price_precision *= 1e6

    return OraclePriceData(
        price=raw_price_to_price_precision,
        slot=pyth_price_info.pub_slot,
        confidence=convert_pyth_price(pyth_price_info.confidence_interval, scale),
        twap=convert_pyth_price(twap, scale),
        twap_confidence=convert_pyth_price(twac, scale),
        has_sufficient_number_of_datapoints=True,
    )


def get_oracle_decode_fn(oracle_source: OracleSource):
    if "Pyth" in str(oracle_source):
        return lambda data: decode_pyth_price_info(data, oracle_source)
    else:
        raise Exception("Unknown oracle source")
