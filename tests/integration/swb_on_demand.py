from pytest import mark, approx

from solana.rpc.async_api import AsyncClient

from solders.pubkey import Pubkey

from driftpy.accounts.oracle import (
    decode_oracle,
    get_oracle_decode_fn,
    get_oracle_price_data_and_slot,
    SWB_ON_DEMAND_CODER,
)
from driftpy.accounts.types import OracleSource
from driftpy.constants.numeric_constants import SWB_PRECISION


@mark.asyncio
async def test_swb_on_demand():
    oracle = Pubkey.from_string("EZLBfnznMYKjFmaWYMEdhwnkiQF1WiP9jjTY6M8HpmGE")
    oracle_source = OracleSource.SwitchboardOnDemand()
    connection = AsyncClient("https://api.mainnet-beta.solana.com")

    oracle_fetched = await get_oracle_price_data_and_slot(
        connection, oracle, oracle_source
    )

    raw = (await connection.get_account_info(oracle)).value.data
    oracle_unstructured = SWB_ON_DEMAND_CODER.accounts.decode(raw).result

    decode = get_oracle_decode_fn(oracle_source)
    oracle_decode_fn = decode(raw)

    oracle_decode_oracle = decode_oracle(raw, oracle_source)

    # these two should be identical
    assert oracle_decode_oracle.price == oracle_decode_fn.price
    assert oracle_decode_oracle.slot == oracle_decode_fn.slot
    assert oracle_decode_oracle.confidence == oracle_decode_fn.confidence
    assert oracle_decode_oracle.twap == oracle_decode_fn.twap
    assert oracle_decode_oracle.twap_confidence == oracle_decode_fn.twap_confidence
    assert (
        oracle_decode_oracle.has_sufficient_number_of_data_points
        == oracle_decode_fn.has_sufficient_number_of_data_points
    )

    # potential slight diff from slot drift
    assert oracle_fetched.data.price == approx(oracle_decode_oracle.price)
    assert oracle_fetched.data.slot == approx(oracle_decode_oracle.slot)
    assert oracle_fetched.data.confidence == approx(oracle_decode_oracle.confidence)
    assert oracle_fetched.data.twap == oracle_decode_oracle.twap
    assert oracle_fetched.data.twap_confidence == oracle_decode_oracle.twap_confidence
    assert (
        oracle_fetched.data.has_sufficient_number_of_data_points
        == oracle_decode_oracle.has_sufficient_number_of_data_points
    )

    assert oracle_unstructured.value == approx(
        oracle_fetched.data.price * SWB_PRECISION
    )
    assert oracle_unstructured.slot == approx(oracle_fetched.data.slot)
    assert oracle_unstructured.range == approx(
        oracle_fetched.data.confidence * SWB_PRECISION
    )

    assert (oracle_unstructured.value // SWB_PRECISION) == oracle_decode_oracle.price
    assert oracle_unstructured.slot == oracle_decode_oracle.slot
    assert (
        oracle_unstructured.range // SWB_PRECISION
    ) == oracle_decode_oracle.confidence
