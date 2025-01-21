import math
from base64 import b64decode
from dataclasses import dataclass
from typing import Optional

from anchorpy.program.context import Context
from anchorpy.program.core import Program
from anchorpy.provider import Provider
from construct import Int32sl, Int64ul
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import CreateAccountParams, create_account
from spl.token._layouts import ACCOUNT_LAYOUT, MINT_LAYOUT
from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    InitializeAccountParams,
    InitializeMintParams,
    MintToParams,
    initialize_account,
    initialize_mint,
    mint_to,
)

from driftpy.admin import Admin
from driftpy.constants.numeric_constants import (
    QUOTE_PRECISION,
    SPOT_MARKET_WEIGHT_PRECISION,
    SPOT_RATE_PRECISION,
)
from driftpy.math.amm import calculate_amm_reserves_after_swap, calculate_price
from driftpy.types import (
    AssetType,
    OracleSource,
    PerpMarketAccount,
    PositionDirection,
    SwapDirection,
)

NATIVE_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")


async def adjust_oracle_pretrade(
    baa: int,
    position_direction: PositionDirection,
    market: PerpMarketAccount,
    oracle_program: Program,
):
    price = calculate_price(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        market.amm.peg_multiplier,
    )
    swap_direction = (
        SwapDirection.Add
        if position_direction == PositionDirection.Short()  # type: ignore
        else SwapDirection.Remove
    )
    new_qar, new_bar = calculate_amm_reserves_after_swap(
        market.amm,
        AssetType.BASE,  # type: ignore
        abs(baa),
        swap_direction,  # type: ignore
    )
    newprice = calculate_price(new_bar, new_qar, market.amm.peg_multiplier)
    await set_price_feed(oracle_program, market.amm.oracle, newprice)
    print(f"oracle: {price} -> {newprice}")

    return newprice


async def _airdrop_user(
    provider: Provider, user: Optional[Keypair] = None
) -> tuple[Keypair, Signature]:
    if user is None:
        user = Keypair()
    resp = await provider.connection.request_airdrop(user.pubkey(), 100_0 * 1000000000)
    tx_sig = resp.value
    return user, tx_sig


async def _create_mint(provider: Provider) -> Keypair:
    fake_create_mint = Keypair()
    params = CreateAccountParams(
        from_pubkey=provider.wallet.public_key,
        to_pubkey=fake_create_mint.pubkey(),
        lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_mint(
            provider.connection
        ),
        space=MINT_LAYOUT.sizeof(),
        owner=TOKEN_PROGRAM_ID,
    )
    create_create_mint_account_ix = create_account(params)
    init_collateral_mint_ix = initialize_mint(
        InitializeMintParams(
            decimals=6,
            program_id=TOKEN_PROGRAM_ID,
            mint=fake_create_mint.pubkey(),
            mint_authority=provider.wallet.public_key,
            freeze_authority=None,
        )
    )

    fake_tx = Transaction(
        instructions=[create_create_mint_account_ix, init_collateral_mint_ix],
        recent_blockhash=(
            await provider.connection.get_latest_blockhash()
        ).value.blockhash,
        fee_payer=provider.wallet.public_key,
    )

    fake_tx.sign_partial(fake_create_mint)
    provider.wallet.sign_transaction(fake_tx)
    await provider.send(fake_tx)
    return fake_create_mint


async def _create_user_ata_tx(
    account: Keypair, provider: Provider, mint: Keypair, owner: Pubkey
) -> Transaction:
    fake_tx = Transaction()

    create_token_account_ix = create_account(
        CreateAccountParams(
            from_pubkey=provider.wallet.public_key,
            to_pubkey=account.pubkey(),
            lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_account(
                provider.connection
            ),
            space=ACCOUNT_LAYOUT.sizeof(),
            owner=TOKEN_PROGRAM_ID,
        )
    )
    fake_tx.add(create_token_account_ix)

    init_token_account_ix = initialize_account(
        InitializeAccountParams(
            program_id=TOKEN_PROGRAM_ID,
            account=account.pubkey(),
            mint=mint.pubkey(),
            owner=owner,
        )
    )
    fake_tx.add(init_token_account_ix)

    return fake_tx


def mint_ix(
    usdc_mint: Pubkey,
    mint_auth: Pubkey,
    usdc_amount: int,
    ata_account: Pubkey,
) -> Instruction:
    mint_to_user_account_ix = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=usdc_mint,
            dest=ata_account,
            mint_authority=mint_auth,
            signers=[],
            amount=usdc_amount,
        )
    )
    return mint_to_user_account_ix


def _mint_usdc_tx(
    usdc_mint: Keypair,
    provider: Provider,
    usdc_amount: int,
    ata_account: Pubkey,
) -> Transaction:
    fake_usdc_tx = Transaction()

    mint_to_user_account_tx = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=usdc_mint.pubkey(),
            dest=ata_account,
            mint_authority=provider.wallet.public_key,
            signers=[],
            amount=usdc_amount,
        )
    )
    fake_usdc_tx.add(mint_to_user_account_tx)

    return fake_usdc_tx


async def _create_and_mint_user_usdc(
    usdc_mint: Keypair, provider: Provider, usdc_amount: int, owner: Pubkey
) -> Keypair:
    usdc_account = Keypair()

    ata_tx: Transaction = await _create_user_ata_tx(
        usdc_account,
        provider,
        usdc_mint,
        owner,
    )
    mint_tx: Transaction = _mint_usdc_tx(
        usdc_mint, provider, usdc_amount, usdc_account.pubkey()
    )

    for ix in mint_tx.instructions:
        ata_tx.add(ix)

    ata_tx.recent_blockhash = (
        await provider.connection.get_latest_blockhash()
    ).value.blockhash
    ata_tx.fee_payer = provider.wallet.payer.pubkey()

    ata_tx.sign_partial(usdc_account)
    ata_tx.sign(provider.wallet.payer)

    await provider.send(ata_tx)

    return usdc_account


async def set_price_feed(
    oracle_program: Program,
    oracle_public_key: Pubkey,
    price: float,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10**-data.exponent)
    return await oracle_program.rpc["set_price"](
        int_price, ctx=Context(accounts={"price": oracle_public_key})
    )


async def set_price_feed_detailed(
    oracle_program: Program,
    oracle_public_key: Pubkey,
    price: float,
    conf: float,
    slot: int,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10**-data.exponent)
    int_conf = int(abs(conf) * 10**-data.exponent)
    print("setting oracle price", int_price, "+/-", int_conf, "@ slot=", slot)
    return await oracle_program.rpc["set_price_info"](
        int_price, int_conf, slot, ctx=Context(accounts={"price": oracle_public_key})
    )


async def get_set_price_feed_detailed_ix(
    oracle_program: Program,
    oracle_public_key: Pubkey,
    price: float,
    conf: float,
    slot: int,
):
    data = await get_feed_data(oracle_program, oracle_public_key)
    int_price = int(price * 10**-data.exponent)
    int_conf = int(abs(conf) * 10**-data.exponent)
    print("setting oracle price", int_price, "+/-", int_conf, "@ slot=", slot)
    return oracle_program.instruction["set_price_info"](
        int_price, int_conf, slot, ctx=Context(accounts={"price": oracle_public_key})
    )


async def create_price_feed(
    oracle_program: Program,
    init_price: int,
    confidence: Optional[int] = None,
    expo: int = -4,
) -> Pubkey:
    conf = int((init_price / 10) * 10**-expo) if confidence is None else confidence
    collateral_token_feed = Keypair()
    space = 3312
    mbre_resp = (
        await oracle_program.provider.connection.get_minimum_balance_for_rent_exemption(
            space
        )
    )
    lamports = mbre_resp.value
    await oracle_program.rpc["initialize"](
        int(init_price * 10**-expo),
        expo,
        conf,
        ctx=Context(
            accounts={"price": collateral_token_feed.pubkey()},
            signers=[collateral_token_feed],
            pre_instructions=[
                create_account(
                    CreateAccountParams(
                        from_pubkey=oracle_program.provider.wallet.public_key,
                        to_pubkey=collateral_token_feed.pubkey(),
                        space=space,
                        lamports=lamports,
                        owner=oracle_program.program_id,
                    )
                ),
            ],
        ),
    )
    return collateral_token_feed.pubkey()


@dataclass
class PriceData:
    exponent: int
    price: int


def parse_price_data(data: bytes) -> PriceData:
    exponent = Int32sl.parse(data[20:24])
    raw_price = Int64ul.parse(data[208:216])
    price = raw_price * 10**exponent
    return PriceData(exponent, price)


async def get_feed_data(oracle_program: Program, price_feed: Pubkey) -> PriceData:
    info_resp = await oracle_program.provider.connection.get_account_info(price_feed)
    if info_resp.value is None:
        raise Exception("No account info found")
    return parse_price_data(info_resp.value.data)


async def get_oracle_data(
    connection: AsyncClient,
    oracle_addr: Pubkey,
):
    info_resp = await connection.get_account_info(oracle_addr)
    if info_resp.value is None:
        raise Exception("No account info found")
    return parse_price_data(b64decode(info_resp.value.data))


async def mock_oracle(
    pyth_program: Program, price: int = int(50 * 10e7), expo=-7
) -> Pubkey:
    price_feed_address = await create_price_feed(
        oracle_program=pyth_program, init_price=price, expo=expo
    )

    feed_data = await get_feed_data(pyth_program, price_feed_address)

    assert math.isclose(
        feed_data.price, price, abs_tol=0.001
    ), f"{feed_data.price} {price}"
    return price_feed_address


async def initialize_sol_spot_market(
    admin: Admin,
    sol_oracle: Pubkey,
    sol_mint: Pubkey = NATIVE_MINT,
    oracle_source: OracleSource = OracleSource.Pyth(),  # type: ignore
):
    optimal_utilization = SPOT_RATE_PRECISION // 2
    optimal_rate = SPOT_RATE_PRECISION * 20
    max_rate = SPOT_RATE_PRECISION * 50
    initial_asset_weight = (SPOT_MARKET_WEIGHT_PRECISION * 8) // 10
    maintenance_asset_weight = (SPOT_MARKET_WEIGHT_PRECISION * 9) // 10
    initial_liability_weight = (SPOT_MARKET_WEIGHT_PRECISION * 12) // 10
    maintenance_liability_weight = (SPOT_MARKET_WEIGHT_PRECISION * 11) // 10

    market_index = admin.get_state_account().number_of_markets  # type: ignore

    sig = await admin.initialize_spot_market(
        sol_mint,
        optimal_utilization,
        optimal_rate,
        max_rate,
        sol_oracle,
        oracle_source,
        initial_asset_weight,
        maintenance_asset_weight,
        initial_liability_weight,
        maintenance_liability_weight,
    )

    await admin.update_withdraw_guard_threshold(
        market_index, (10**10) * QUOTE_PRECISION
    )

    return sig


async def initialize_quote_spot_market(
    admin: Admin,
    usdc_mint: Pubkey,
):
    optimal_utilization = SPOT_RATE_PRECISION // 2
    optimal_rate = SPOT_RATE_PRECISION
    max_rate = SPOT_RATE_PRECISION
    initial_asset_weight = SPOT_MARKET_WEIGHT_PRECISION
    maintenance_asset_weight = SPOT_MARKET_WEIGHT_PRECISION
    initial_liability_weight = SPOT_MARKET_WEIGHT_PRECISION
    maintenance_liability_weight = SPOT_MARKET_WEIGHT_PRECISION
    imf_factor = 0

    market_index = admin.get_state_account().number_of_markets  # type: ignore

    sig = await admin.initialize_spot_market(
        usdc_mint,
        optimal_utilization,
        optimal_rate,
        max_rate,
        Pubkey.default(),
        OracleSource.QuoteAsset(),  # type: ignore
        initial_asset_weight,
        maintenance_asset_weight,
        initial_liability_weight,
        maintenance_liability_weight,
        imf_factor,
    )
    await admin.update_withdraw_guard_threshold(
        market_index, (10**10) * QUOTE_PRECISION
    )

    return sig
