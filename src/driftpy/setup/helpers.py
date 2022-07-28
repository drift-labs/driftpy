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

from driftpy.types import Market, PositionDirection, SwapDirection, AssetType
from driftpy.math.amm import calculate_amm_reserves_after_swap, calculate_price

async def adjust_oracle_pretrade(
    baa: int, 
    position_direction: PositionDirection, 
    market: Market, 
    oracle_public_key: PublicKey,
    oracle_program: Program,
):
    price = calculate_price(
        market.amm.base_asset_reserve, 
        market.amm.quote_asset_reserve, 
        market.amm.peg_multiplier,
    )
    swap_direction = SwapDirection.ADD if position_direction == PositionDirection.SHORT() else SwapDirection.REMOVE
    new_qar, new_bar = calculate_amm_reserves_after_swap(
        market.amm, 
        AssetType.BASE, 
        baa, 
        swap_direction,
    )
    newprice = calculate_price(new_bar, new_qar, market.amm.peg_multiplier)
    await set_price_feed(oracle_program, oracle_public_key, newprice)
    print(f'oracle: {price} -> {newprice}')

    return newprice

async def _setup_user(
    provider: Provider
) -> Keypair:
    user = Keypair()
    resp = await provider.connection.request_airdrop(user.public_key, 100_000 * 1000000000)
    tx_sig = resp['result']
    await provider.connection.confirm_transaction(tx_sig, commitment=Processed, sleep_seconds=0)
    return user

async def _usdc_mint(provider: Provider) -> Keypair:
    fake_usdc_mint = Keypair()
    params = CreateAccountParams(
        from_pubkey=provider.wallet.public_key,
        new_account_pubkey=fake_usdc_mint.public_key,
        lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_mint(
            provider.connection
        ),
        space=MINT_LAYOUT.sizeof(),
        program_id=TOKEN_PROGRAM_ID,
    )
    create_usdc_mint_account_ix = create_account(params)
    init_collateral_mint_ix = initialize_mint(
        InitializeMintParams(
            decimals=6,
            program_id=TOKEN_PROGRAM_ID,
            mint=fake_usdc_mint.public_key,
            mint_authority=provider.wallet.public_key,
            freeze_authority=None,
        )
    )
    fake_usdc_tx = Transaction().add(
        create_usdc_mint_account_ix, init_collateral_mint_ix
    )
    await provider.send(fake_usdc_tx, [fake_usdc_mint])
    return fake_usdc_mint

async def _user_usdc_account(
    usdc_mint: Keypair,
    provider: Provider,
    usdc_amount: int, 
    owner: PublicKey = None
) -> Keypair:
    account = Keypair()
    fake_usdc_tx = Transaction()

    if owner is None:
        owner = provider.wallet.public_key

    create_usdc_token_account_ix = create_account(
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
    fake_usdc_tx.add(create_usdc_token_account_ix)

    init_usdc_token_account_ix = initialize_account(
        InitializeAccountParams(
            program_id=TOKEN_PROGRAM_ID,
            account=account.public_key,
            mint=usdc_mint.public_key,
            owner=owner,
        )
    )
    fake_usdc_tx.add(init_usdc_token_account_ix)

    mint_to_user_account_tx = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=usdc_mint.public_key,
            dest=account.public_key,
            mint_authority=provider.wallet.public_key,
            signers=[],
            amount=usdc_amount,
        )
    )
    fake_usdc_tx.add(mint_to_user_account_tx)

    await provider.send(fake_usdc_tx, [provider.wallet.payer, account])
    return account

async def set_price_feed(
    oracle_program: Program,
    oracle_public_key: PublicKey,
    price: float,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10 ** -data.exponent)
    return await oracle_program.rpc["set_price"](
        int_price,
        ctx=Context(
            accounts={"price": oracle_public_key }
        )
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
    return parse_price_data(b64decode(info_resp["result"]["value"]["data"][0]))


async def mock_oracle(
    pyth_program: Program, price: int = int(50 * 10e7), expo=-7
) -> PublicKey:
    price_feed_address = await create_price_feed(
        oracle_program=pyth_program, init_price=price, expo=expo
    )

    feed_data = await get_feed_data(pyth_program, price_feed_address)

    assert math.isclose(feed_data.price, price, abs_tol=0.001), f"{feed_data.price} {price}"
    return price_feed_address
