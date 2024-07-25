from pytest import mark, approx

from solana.rpc.async_api import AsyncClient

from solders.pubkey import Pubkey

from driftpy.accounts.oracle import (
    decode_oracle,
    get_oracle_decode_fn,
    get_oracle_price_data_and_slot,
)
from driftpy.accounts.types import OracleSource


@mark.asyncio
async def test_swb_on_demand():
    oracle = Pubkey.from_string("EZLBfnznMYKjFmaWYMEdhwnkiQF1WiP9jjTY6M8HpmGE")
    oracle_source = OracleSource.SwitchboardOnDemand()
    connection = AsyncClient("https://api.mainnet-beta.solana.com")

    oracle_get_oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
        connection, oracle, oracle_source
    )

    raw = (await connection.get_account_info(oracle)).value.data
    decode = get_oracle_decode_fn(oracle_source)
    oracle_decode_fn = decode(raw)

    oracle_decode_oracle = decode_oracle(raw, oracle_source)

    assert oracle_decode_oracle.price == oracle_decode_fn.price
    assert oracle_decode_oracle.slot == oracle_decode_fn.slot
    assert oracle_decode_oracle.confidence == oracle_decode_fn.confidence
    assert oracle_decode_oracle.twap == oracle_decode_fn.twap
    assert oracle_decode_oracle.twap_confidence == oracle_decode_fn.twap_confidence
    assert (
        oracle_decode_oracle.has_sufficient_number_of_data_points
        == oracle_decode_fn.has_sufficient_number_of_data_points
    )

    assert oracle_get_oracle_price_data_and_slot.data.price == approx(
        oracle_decode_oracle.price
    )
    assert oracle_get_oracle_price_data_and_slot.data.slot == approx(
        oracle_decode_oracle.slot
    )
    assert oracle_get_oracle_price_data_and_slot.data.confidence == approx(
        oracle_decode_oracle.confidence
    )
    assert oracle_get_oracle_price_data_and_slot.data.twap == oracle_decode_oracle.twap
    assert (
        oracle_get_oracle_price_data_and_slot.data.twap_confidence
        == oracle_decode_oracle.twap_confidence
    )
    assert (
        oracle_get_oracle_price_data_and_slot.data.has_sufficient_number_of_data_points
        == oracle_decode_oracle.has_sufficient_number_of_data_points
    )
