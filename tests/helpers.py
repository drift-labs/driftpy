from base64 import b64decode
from dataclasses import dataclass
from typing import Optional
from construct import Int32sl, Int64ul
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.system_program import create_account, CreateAccountParams
from anchorpy import Program, Context


async def create_price_feed(
    oracle_program: Program,
    init_price: int,
    confidence: Optional[int] = None,
    expo: Optional[int] = -4,
) -> PublicKey:
    conf = int((init_price / 10) * 10 ** -expo) if confidence is None else confidence
    collateral_token_feed = Keypair()
    space = 3312
    mbre_resp = (
        await oracle_program.provider.connection.get_minimum_balance_for_rent_exemption(
            space
        )
    )
    lamports = mbre_resp["result"]
    await oracle_program.rpc["initialize"](
        int(init_price * 10 ** -expo),
        expo,
        conf,
        ctx=Context(
            accounts={"price": collateral_token_feed.public_key},
            signers=[collateral_token_feed],
            pre_instructions=[
                create_account(
                    CreateAccountParams(
                        from_pubkey=oracle_program.provider.wallet.public_key,
                        new_account_pubkey=collateral_token_feed.public_key,
                        space=space,
                        lamports=lamports,
                        program_id=oracle_program.program_id,
                    )
                ),
            ],
        ),
    )
    return collateral_token_feed.public_key


@dataclass
class PriceData:
    exponent: int
    price: int


def parse_price_data(data: bytes) -> PriceData:
    exponent = Int32sl.parse(data[20:24])
    raw_price = Int64ul.parse(data[208:216])
    price = raw_price * 10 ** exponent
    return PriceData(exponent, price)


async def get_feed_data(oracle_program: Program, price_feed: PublicKey) -> PriceData:
    info_resp = await oracle_program.provider.connection.get_account_info(price_feed)
    return parse_price_data(b64decode(info_resp["result"]["value"]["data"][0]))


async def mock_oracle(
    pyth_program: Program, price: int = 50 * 10e7, expo=-7
) -> PublicKey:
    price_feed_address = await create_price_feed(
        oracle_program=pyth_program, init_price=price, expo=expo
    )

    feed_data = await get_feed_data(pyth_program, price_feed_address)
    assert feed_data.price == price
    return price_feed_address
