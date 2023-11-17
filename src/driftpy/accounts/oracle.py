from solders.rpc.responses import GetAccountInfoResp

from .types import DataAndSlot
from driftpy.constants.numeric_constants import *
from driftpy.types import OracleSource, OraclePriceData

from solders.pubkey import Pubkey
from pythclient.pythaccounts import PythPriceInfo, _ACCOUNT_HEADER_BYTES, EmaType
from solana.rpc.async_api import AsyncClient
import base64
import struct


def convert_pyth_price(price, scale=1):
    return int(price * PRICE_PRECISION * scale)


async def get_oracle_price_data_and_slot(
    connection: AsyncClient, address: Pubkey, oracle_source=OracleSource.PYTH()
) -> DataAndSlot[OraclePriceData]:
    if "Pyth" in str(oracle_source):
        rpc_reponse = await connection.get_account_info(address)
        rpc_response_slot = rpc_reponse.context.slot
        (pyth_price_info, last_slot, twac, twap) = await _parse_pyth_price_info(
            rpc_reponse
        )

        scale = 1
        if "1K" in str(oracle_source):
            scale = 1e3
        elif "1M" in str(oracle_source):
            scale = 1e6

        oracle_data = OraclePriceData(
            price=convert_pyth_price(pyth_price_info.price, scale),
            slot=pyth_price_info.pub_slot,
            confidence=convert_pyth_price(pyth_price_info.confidence_interval, scale),
            twap=convert_pyth_price(twap, scale),
            twap_confidence=convert_pyth_price(twac, scale),
            has_sufficient_number_of_datapoints=True,
        )

        return DataAndSlot(data=oracle_data, slot=rpc_response_slot)
    elif "Quote" in str(oracle_source):
        return DataAndSlot(
            data=OraclePriceData(PRICE_PRECISION, 0, 1, 1, 0, True), slot=0
        )
    else:
        raise NotImplementedError("Unsupported Oracle Source", str(oracle_source))


async def _parse_pyth_price_info(
    resp: GetAccountInfoResp,
) -> (PythPriceInfo, int, int, int):
    buffer = resp.value.data

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

    return (
        PythPriceInfo.deserialise(buffer, offset, exponent=exponent),
        last_slot,
        twac,
        twap,
    )
