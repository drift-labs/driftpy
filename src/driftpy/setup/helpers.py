from base64 import b64decode
from dataclasses import dataclass
from typing import Optional
from construct import Int32sl, Int64ul
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.system_program import create_account, CreateAccountParams
from anchorpy import Program, Context, Provider
from solana.keypair import Keypair
from solana.transaction import Transaction
from solana.system_program import create_account, CreateAccountParams
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token._layouts import MINT_LAYOUT
from spl.token.async_client import AsyncToken
from spl.token.instructions import initialize_mint, InitializeMintParams
import math

from solana.system_program import create_account, CreateAccountParams
from spl.token.async_client import AsyncToken
from spl.token._layouts import ACCOUNT_LAYOUT
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    initialize_account,
    InitializeAccountParams,
    mint_to,
    MintToParams,
)
from solana.rpc.commitment import Processed, Finalized, Confirmed
from solana.transaction import TransactionSignature

from driftpy.sdk_types import AssetType
from driftpy.types import *
from driftpy.math.amm import calculate_amm_reserves_after_swap, calculate_price


async def adjust_oracle_pretrade(
    baa: int,
    position_direction: PositionDirection,
    market: PerpMarket,
    oracle_program: Program,
):
    price = calculate_price(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        market.amm.peg_multiplier,
    )
    swap_direction = (
        SwapDirection.ADD
        if position_direction == PositionDirection.SHORT()
        else SwapDirection.REMOVE
    )
    new_qar, new_bar = calculate_amm_reserves_after_swap(
        market.amm,
        AssetType.BASE,
        abs(baa),
        swap_direction,
    )
    newprice = calculate_price(new_bar, new_qar, market.amm.peg_multiplier)
    await set_price_feed(oracle_program, market.amm.oracle, newprice)
    print(f"oracle: {price} -> {newprice}")

    return newprice


async def _airdrop_user(
    provider: Provider, user: Optional[Keypair] = None
) -> tuple[Keypair, TransactionSignature]:
    if user is None:
        user = Keypair()
    resp = await provider.connection.request_airdrop(
        user.public_key, 100_0 * 1000000000
    )
    tx_sig = resp["result"]
    return user, tx_sig


async def _create_mint(provider: Provider) -> Keypair:
    fake_create_mint = Keypair()
    params = CreateAccountParams(
        from_pubkey=provider.wallet.public_key,
        new_account_pubkey=fake_create_mint.public_key,
        lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_mint(
            provider.connection
        ),
        space=MINT_LAYOUT.sizeof(),
        program_id=TOKEN_PROGRAM_ID,
    )
    create_create_mint_account_ix = create_account(params)
    init_collateral_mint_ix = initialize_mint(
        InitializeMintParams(
            decimals=6,
            program_id=TOKEN_PROGRAM_ID,
            mint=fake_create_mint.public_key,
            mint_authority=provider.wallet.public_key,
            freeze_authority=None,
        )
    )
    fake_tx = Transaction().add(create_create_mint_account_ix, init_collateral_mint_ix)
    await provider.send(fake_tx, [fake_create_mint])
    return fake_create_mint


async def _create_user_ata_tx(
    account: Keypair, provider: Provider, mint: Keypair, owner: PublicKey
) -> Transaction:
    fake_tx = Transaction()

    create_token_account_ix = create_account(
        CreateAccountParams(
            from_pubkey=provider.wallet.public_key,
            new_account_pubkey=account.public_key,
            lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_account(
                provider.connection
            ),
            space=ACCOUNT_LAYOUT.sizeof(),
            program_id=TOKEN_PROGRAM_ID,
        )
    )
    fake_tx.add(create_token_account_ix)

    init_token_account_ix = initialize_account(
        InitializeAccountParams(
            program_id=TOKEN_PROGRAM_ID,
            account=account.public_key,
            mint=mint.public_key,
            owner=owner,
        )
    )
    fake_tx.add(init_token_account_ix)

    return fake_tx

def mint_ix(
    usdc_mint: PublicKey,
    mint_auth: PublicKey,
    usdc_amount: int,
    ata_account: PublicKey,
) -> Transaction:
    mint_to_user_account_tx = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=usdc_mint,
            dest=ata_account,
            mint_authority=mint_auth,
            signers=[],
            amount=usdc_amount,
        )
    )
    return mint_to_user_account_tx

def _mint_usdc_tx(
    usdc_mint: Keypair,
    provider: Provider,
    usdc_amount: int,
    ata_account: PublicKey,
) -> Transaction:
    fake_usdc_tx = Transaction()

    mint_to_user_account_tx = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=usdc_mint.public_key,
            dest=ata_account,
            mint_authority=provider.wallet.public_key,
            signers=[],
            amount=usdc_amount,
        )
    )
    fake_usdc_tx.add(mint_to_user_account_tx)

    return fake_usdc_tx


async def _create_and_mint_user_usdc(
    usdc_mint: Keypair, provider: Provider, usdc_amount: int, owner: PublicKey
) -> Keypair:
    usdc_account = Keypair()

    ata_tx: Transaction = await _create_user_ata_tx(
        usdc_account,
        provider,
        usdc_mint,
        owner,
    )
    mint_tx: Transaction = _mint_usdc_tx(
        usdc_mint, provider, usdc_amount, usdc_account.public_key
    )

    for ix in mint_tx.instructions:
        ata_tx.add(ix)

    await provider.send(ata_tx, [provider.wallet.payer, usdc_account])

    return usdc_account


async def set_price_feed(
    oracle_program: Program,
    oracle_public_key: PublicKey,
    price: float,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10 ** -data.exponent)
    print("setting oracle price", int_price)
    return await oracle_program.rpc["set_price"](
        int_price, ctx=Context(accounts={"price": oracle_public_key})
    )


async def set_price_feed_detailed(
    oracle_program: Program,
    oracle_public_key: PublicKey,
    price: float,
    conf: float,
    slot: int,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10 ** -data.exponent)
    int_conf = int(abs(conf) * 10 ** -data.exponent)
    print("setting oracle price", int_price, "+/-", int_conf, "@ slot=", slot)
    return await oracle_program.rpc["set_price_info"](
        int_price, int_conf, slot, ctx=Context(accounts={"price": oracle_public_key})
    )


async def get_set_price_feed_detailed_ix(
    oracle_program: Program,
    oracle_public_key: PublicKey,
    price: float,
    conf: float,
    slot: int,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10 ** -data.exponent)
    int_conf = int(abs(conf) * 10 ** -data.exponent)
    print("setting oracle price", int_price, "+/-", int_conf, "@ slot=", slot)
    return oracle_program.instruction["set_price_info"](
        int_price, int_conf, slot, ctx=Context(accounts={"price": oracle_public_key})
    )


async def create_price_feed(
    oracle_program: Program,
    init_price: int,
    confidence: Optional[int] = None,
    expo: int = -4,
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
    raw_bytes = b64decode(info_resp["result"]["value"]["data"][0])
    return parse_price_data(raw_bytes)


from solana.rpc.async_api import AsyncClient


async def get_oracle_data(
    connection: AsyncClient,
    oracle_addr: PublicKey,
):
    info_resp = await connection.get_account_info(oracle_addr)
    return parse_price_data(b64decode(info_resp["result"]["value"]["data"][0]))


async def mock_oracle(
    pyth_program: Program, price: int = int(50 * 10e7), expo=-7
) -> PublicKey:
    price_feed_address = await create_price_feed(
        oracle_program=pyth_program, init_price=price, expo=expo
    )

    feed_data = await get_feed_data(pyth_program, price_feed_address)

    assert math.isclose(
        feed_data.price, price, abs_tol=0.001
    ), f"{feed_data.price} {price}"
    return price_feed_address
