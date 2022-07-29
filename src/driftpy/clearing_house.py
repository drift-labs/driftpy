from dataclasses import dataclass
import json
from importlib import resources
from typing import Optional, TypeVar, Type, cast
from solana.publickey import PublicKey
from solana.keypair import Keypair
from solana.transaction import Transaction, TransactionSignature, TransactionInstruction
from solana.system_program import SYS_PROGRAM_ID
from solana.sysvar import SYSVAR_RENT_PUBKEY
from solana.transaction import AccountMeta
from spl.token.constants import TOKEN_PROGRAM_ID
from anchorpy import Program, Context, Idl
from struct import pack_into 

from driftpy.constants.numeric_constants import QUOTE_ASSET_BANK_INDEX
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
    MakerInfo
)

from driftpy.accounts import (
    get_market_account, 
    get_bank_account,
    get_user_account
)

from anchorpy import Wallet

DEFAULT_USER_NAME = 'Main Account'

def is_available(position: MarketPosition): 
    return (
        position.base_asset_amount == 0 and
        position.open_orders == 0 and 
        position.lp_shares == 0
    )
    
class ClearingHouse:
    """This class is the main way to interact with Drift Protocol.

    It allows you to subscribe to the various accounts where the Market's state is
    stored, as well as: opening positions, liquidating, settling funding, depositing &
    withdrawing, and more.

    The default way to construct a ClearingHouse instance is using the
    [create][driftpy.clearing_house.ClearingHouse.create] method.
    """

    def __init__(self, program: Program, authority: Keypair = None):
        """Initialize the ClearingHouse object.

        Note: you probably want to use
        [create][driftpy.clearing_house.ClearingHouse.create]
        instead of this method.

        Args:
            program: The AnchorPy program object.
            pdas: The required PDAs for the ClearingHouse object.
        """
        self.program = program
        self.program_id = program.program_id

        if authority is None: 
            authority = program.provider.wallet.payer

        self.signer = authority
        self.authority = authority.public_key

    async def send_ixs(self, ixs: list[TransactionInstruction]):
        tx = Transaction()
        for ix in ixs:
            tx.add(ix)
        return await self.program.provider.send(tx, signers=[self.signer])

    async def intialize_user(
        self, 
        user_id: int = 0 
    ):
        ix = self.get_initialize_user_instructions(user_id)
        return await self.send_ixs([ix])

    def get_initialize_user_instructions(
        self,
        user_id: int = 0, 
        name: str = DEFAULT_USER_NAME
    ) -> TransactionInstruction:
        user_public_key = get_user_account_public_key(
            self.program_id, 
            self.authority,
            user_id
        )
        state_public_key = get_state_public_key(
            self.program_id
        )

        if len(name) > 32: 
            raise Exception("name too long")

        name_bytes = bytearray(32)
        pack_into(f'{len(name)}s', name_bytes, 0, name.encode('utf-8'))
        offset = len(name)
        for _ in range(32 - len(name)):
            pack_into('1s', name_bytes, offset, ' '.encode('utf-8'))
            offset += 1

        str_name_bytes = name_bytes.hex()
        name_byte_array = []
        for i in range(0, len(str_name_bytes), 2):
            name_byte_array.append(
                int(str_name_bytes[i:i+2], 16)
            )

        initialize_user_account_ix = self.program.instruction["initialize_user"](
            user_id,
            name_byte_array,
            ctx=Context(
                accounts={
                    "user": user_public_key,
                    "authority": self.authority,
                    "payer": self.authority, 
                    "rent": SYSVAR_RENT_PUBKEY,
                    "system_program": SYS_PROGRAM_ID,
                    "state": state_public_key,
                },
            ),
        )
        return initialize_user_account_ix
    
    async def get_remaining_accounts(
        self,
        writable_market_index: int = None, 
        writable_bank_index: int = None, 
        user_id = 0,
        include_oracles: bool = True,
        include_banks: bool = True,
        user_public_key: PublicKey = None,
    ):
        if user_public_key is None: 
            user_public_key = self.authority

        user_account = await get_user_account(
            self.program, 
            user_public_key, 
            user_id
        )

        oracle_map = {}
        bank_map = {}
        market_map = {}

        async def track_market(
            market_index,
            is_writable
        ):
            market = await get_market_account(
                self.program, 
                market_index
            )
            market_map[market_index] = AccountMeta(
                pubkey=market.pubkey, 
                is_signer=False, 
                is_writable=is_writable,
            )

            if include_oracles:
                oracle_map[str(market.pubkey)] = AccountMeta(
                    pubkey=market.amm.oracle, 
                    is_signer=False, 
                    is_writable=False
                )

        async def track_bank(
            bank_index, 
            is_writable
        ):
            bank = await get_bank_account(
                self.program, 
                bank_index
            )
            bank_map[bank_index] = AccountMeta(
                pubkey=bank.pubkey, 
                is_signer=False, 
                is_writable=is_writable,
            )

            if bank_index != 0 and include_oracles:
                oracle_map[str(bank.pubkey)] = AccountMeta(
                    pubkey=bank.amm.oracle, 
                    is_signer=False, 
                    is_writable=False
                )

        for position in user_account.positions:
            if not is_available(position):
                market_index = position.market_index
                await track_market(market_index, is_writable=True)

        if writable_market_index is not None: 
            await track_market(writable_market_index, is_writable=True)

        if include_banks:
            for bank_balance in user_account.bank_balances:
                if bank_balance.balance != 0: 
                    await track_bank(bank_balance.bank_index, is_writable=False)

            if writable_bank_index is not None: 
                await track_bank(writable_bank_index, is_writable=True)

        remaining_accounts = [
            *oracle_map.values(), 
            *bank_map.values(), 
            *market_map.values()   
        ]

        return remaining_accounts

    async def deposit(
        self,
        amount: int,
        bank_index: int, 
        user_token_account: PublicKey, 
        user_id: int = 0, 
        reduce_only = False, 
        user_initialized = True,
    ):
        return await self.send_ixs([await self.get_deposit_collateral_ix(
            amount,
            bank_index,
            user_token_account,
            user_id,
            reduce_only,
            user_initialized,
        )])

    async def get_deposit_collateral_ix(
        self,
        amount: int,
        bank_index: int, 
        user_token_account: PublicKey, 
        user_id: int = 0, 
        reduce_only = False, 
        user_initialized = True,
    ) -> TransactionInstruction:

        if user_initialized: 
            remaining_accounts = await self.get_remaining_accounts(
                writable_bank_index=bank_index
            ) 
        else: 
            raise Exception("not implemented...")
                    
        bank = await get_bank_account(
            self.program, 
            bank_index
        )
        user_account_public_key = get_user_account_public_key(
            self.program_id, 
            self.authority, 
            user_id
        )
        return self.program.instruction["deposit"](
            bank_index, 
            amount,
            reduce_only,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id), 
                    "bank": bank.pubkey, 
                    "bank_vault": bank.vault, 
                    "user": user_account_public_key, 
                    "user_token_account": user_token_account, 
                    "authority": self.authority, 
                    "token_program": TOKEN_PROGRAM_ID 
                },
                remaining_accounts=remaining_accounts
            ),
        )
    
    async def add_liquidity(
        self, 
        amount: int, 
        market_index: int, 
        user_id: int = 0
    ):  
        return await self.send_ixs([await self.get_add_liquidity_ix(
            amount, market_index, user_id
        )])

    async def get_add_liquidity_ix(
        self, 
        amount: int, 
        market_index: int, 
        user_id: int = 0
    ):  
        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index
        ) 
        user_account_public_key = get_user_account_public_key(
            self.program_id, 
            self.authority, 
            user_id
        )

        return self.program.instruction["add_liquidity"](
            amount, 
            market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id), 
                    "user": user_account_public_key, 
                    "authority": self.authority, 
                },
                remaining_accounts=remaining_accounts
            ),
        )

    async def remove_liquidity(
        self, 
        amount: int, 
        market_index: int, 
        user_id: int = 0
    ):  
        return await self.send_ixs([await self.get_remove_liquidity_ix(
            amount, market_index, user_id
        )])

    async def get_remove_liquidity_ix(
        self, 
        amount: int, 
        market_index: int, 
        user_id: int = 0
    ):  
        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index, 
            include_oracles=False, 
            include_banks=False,
        ) 
        user_account_public_key = get_user_account_public_key(
            self.program_id, 
            self.authority, 
            user_id
        )

        return self.program.instruction["remove_liquidity"](
            amount, 
            market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id), 
                    "user": user_account_public_key, 
                    "authority": self.authority, 
                },
                remaining_accounts=remaining_accounts
            ),
        )

    async def open_position(
        self,
        direction: PositionDirection, 
        amount: int, 
        market_index: int,
        limit_price: int = 0 
    ): 
       return await self.place_and_take(
            OrderParams(
                order_type=OrderType.LIMIT(), 
                direction=direction, 
                market_index=market_index, 
                base_asset_amount=amount,
                price=limit_price
            )
       ) 

    async def place_and_take(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
    ):
        return await self.send_ixs(
            [await self.get_place_and_take_ix(order_params, maker_info)]
        )

    async def get_place_and_take_ix(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
    ):
        user_account_public_key = get_user_account_public_key(
            self.program_id, 
            self.authority
        )

        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=order_params.market_index, 
            writable_bank_index=QUOTE_ASSET_BANK_INDEX
        ) 

        maker_order_id = None 
        if maker_info is not None: 
            maker_order_id = maker_info.order.order_id
            remaining_accounts.append(AccountMeta(
                pubkey=maker_info.maker, 
                is_signer=False, 
                is_writable=True
            ))

        return self.program.instruction["place_and_take"](
            order_params,
            maker_order_id,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id), 
                    "user": user_account_public_key, 
                    "authority": self.authority, 
                },
                remaining_accounts=remaining_accounts
            ),
        )

    async def settle_lp(
        self,
        settlee_user_account_public_key: PublicKey, 
        market_index: int,
    ): 
        return await self.send_ixs([await self.get_settle_lp_ix(
            settlee_user_account_public_key, 
            market_index
        )])

    async def get_settle_lp_ix(
        self,
        settlee_user_account_public_key: PublicKey, 
        market_index: int,
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index, 
            include_banks=False, 
            include_oracles=False,
            user_public_key=settlee_user_account_public_key,
        ) 

        return self.program.instruction["settle_lp"](
            market_index, 
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id), 
                    "user": get_user_account_public_key(
                        self.program_id, 
                        settlee_user_account_public_key
                    ), 
                },
                remaining_accounts=remaining_accounts
            ),
        )

    async def get_user_position(
        self, 
        market_index: int, 
    ):
        user = await get_user_account(
            self.program, 
            self.authority
        )
        for position in user.positions:
            if position.market_index == market_index:
                break 
        assert position.market_index == market_index, "no position in market"
        
        return position

    async def close_position(
        self, 
        market_index: int
    ):
        position = await self.get_user_position(
            market_index
        )
        if position.base_asset_amount == 0:
            return 

        limit_price = {
            True: 100 * 1e13, # going long
            False: 100e6 # going short
        }[position.base_asset_amount < 0]

        return await self.place_and_take(OrderParams(
                order_type=OrderType.LIMIT(), 
                direction=PositionDirection.LONG() if position.base_asset_amount < 0 else PositionDirection.SHORT(), 
                market_index=market_index, 
                base_asset_amount=abs(int(position.base_asset_amount)),
                price=int(limit_price)
        ))
