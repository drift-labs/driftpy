import pytest
import asyncio
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from anchorpy import Provider, WorkspaceType, workspace_fixture, Program
from solana.keypair import Keypair
from solana.transaction import Transaction
from solana.system_program import create_account, CreateAccountParams
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token._layouts import MINT_LAYOUT
from spl.token.async_client import AsyncToken
from spl.token.instructions import initialize_mint, InitializeMintParams

from driftpy.admin import Admin
from driftpy.constants.numeric_constants import MARK_PRICE_PRECISION
from math import sqrt
from typing import cast
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.transaction import Transaction
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
from anchorpy import Program, Provider, WorkspaceType
from anchorpy.utils.token import get_token_account

from driftpy.admin import Admin
from driftpy.constants.numeric_constants import MARK_PRICE_PRECISION
from driftpy.clearing_house import ClearingHouse

from driftpy.addresses import (
    get_market_public_key,
    get_bank_public_key,
    get_bank_vault_public_key,
    get_bank_vault_authority_public_key,
    get_state_public_key,
    get_user_account_public_key,
) 

from driftpy.types import (
    PriceDivergence,
    Validity,
    OracleGuardRails,
    DiscountTokenTier,
    DiscountTokenTiers,
    ReferralDiscount,
    OrderFillerRewardStructure,
    FeeStructure,
    StateAccount,
    OracleSource,
    DepositDirection,
    TradeDirection,
    OrderType,
    OrderStatus,
    OrderDiscountTier,
    OrderTriggerCondition,
    OrderAction,
    PositionDirection,
    SwapDirection,
    AssetType,
    BankBalanceType,
    Order,
    OrderParamsOptionalAccounts,
    OrderParams,
    OrderFillerRewardStructure,
    MarketPosition,
    UserFees,
    UserBankBalance,
    User,
    PoolBalance,
    Bank,
    AMM,
    Market,
)
from driftpy.accounts import (
    get_market_account, 
    get_bank_account,
    get_user_account
)

from helpers import mock_oracle

MANTISSA_SQRT_SCALE = int(sqrt(MARK_PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * 10 ** 13) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * 10 ** 13) * MANTISSA_SQRT_SCALE)
PERIODICITY = 60 * 60  # 1 HOUR
USDC_AMOUNT = int(10 * 10 ** 6)
MARKET_INDEX = 0

workspace = workspace_fixture(
    "protocol-v2", build_cmd="anchor build --skip-lint", scope="session"
)


@async_fixture(scope="session")
async def usdc_mint(provider: Provider) -> Keypair:
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


@async_fixture(scope="module")
async def user_usdc_account(
    usdc_mint: Keypair,
    provider: Provider,
) -> Keypair:
    account = Keypair()
    fake_usdc_tx = Transaction()

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
            amount=USDC_AMOUNT,
        )
    )
    fake_usdc_tx.add(mint_to_user_account_tx)

    await provider.send(fake_usdc_tx, [provider.wallet.payer, account])
    return account


@fixture(scope="session")
def program(workspace: WorkspaceType) -> Program:
    """Create a Program instance."""
    return workspace["clearing_house"]

@fixture(scope="session")
def provider(program: Program) -> Provider:
    return program.provider

@async_fixture(scope="session")
async def clearing_house(program: Program, usdc_mint: Keypair) -> Admin:
    admin = Admin(program)
    await admin.initialize(usdc_mint.public_key, admin_controls_prices=True)
    return admin 

@async_fixture(scope="session")
async def initialized_bank(
    clearing_house: Admin, 
    usdc_mint: Keypair,
): 
    await clearing_house.initialize_bank(
        usdc_mint.public_key, 
    )

@async_fixture(scope="session")
async def initialized_market(
    clearing_house: Admin, workspace: WorkspaceType
) -> PublicKey:
    pyth_program = workspace["pyth"]
    sol_usd = await mock_oracle(pyth_program=pyth_program, price=1)

    await clearing_house.initialize_market(
        sol_usd,
        AMM_INITIAL_BASE_ASSET_AMOUNT,
        AMM_INITIAL_QUOTE_ASSET_AMOUNT,
        PERIODICITY,
    )

    return sol_usd

@mark.asyncio
async def test_bank(
    clearing_house: Admin,
    initialized_bank: PublicKey,
):
    program = clearing_house.program
    bank: Bank = await get_bank_account(program, 0)
    assert bank.bank_index == 0 

@mark.asyncio
async def test_market(
    clearing_house: Admin,
    initialized_market: PublicKey,
):
    program = clearing_house.program
    market_oracle_public_key = initialized_market
    market_pk = get_market_public_key(program.program_id, 0)
    market: Market = await get_market_account(program, 0)

    assert market.amm.oracle == market_oracle_public_key

@mark.asyncio
async def test_init_user(
    clearing_house: Admin,
):
    await clearing_house.intialize_user()
    user: User = await get_user_account(
        clearing_house.program, 
        clearing_house.authority, 
        user_id=0
    )
    assert user.authority == clearing_house.authority


@mark.asyncio
async def test_usdc_deposit(
    clearing_house: Admin,
    user_usdc_account: Keypair,
):
    await clearing_house.deposit(
        USDC_AMOUNT, 
        0, 
        user_usdc_account, 
    )
    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )
    print(user_account.bank_balances[0].balance)