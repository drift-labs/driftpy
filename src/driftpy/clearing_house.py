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

    def __init__(self, program: Program):
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
        self.authority = program.provider.wallet.public_key

    async def send_ix(self, ixs: list[TransactionInstruction]):
        tx = Transaction()
        for ix in ixs:
            tx.add(ix)
        return await self.program.provider.send(tx)

    async def intialize_user(
        self, 
        user_id: int = 0 
    ):
        ix = self.get_initialize_user_instructions(user_id)
        return await self.send_ix([ix])

    def get_initialize_user_instructions(
        self,
        user_id: int = 0, 
    ) -> TransactionInstruction:
        user_public_key = get_user_account_public_key(
            self.program_id, 
            self.authority,
            user_id
        )
        state_public_key = get_state_public_key(
            self.program_id
        )

        initialize_user_account_ix = self.program.instruction["initialize_user"](
            user_id,
            [0] * 32,
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
    ):
        user_account = await get_user_account(
            self.program, 
            self.authority, 
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
            oracle_map[market.pubkey] = AccountMeta(
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
            if bank_index != 0:
                oracle_map[bank.pubkey] = AccountMeta(
                    pubkey=bank.amm.oracle, 
                    is_signer=False, 
                    is_writable=False
                )

        for position in user_account.positions:
            if not is_available(position):
                market_index = position.market_index
                await track_market(market_index, is_writable=True)

        if writable_market_index: 
            await track_market(writable_market_index, is_writable=True)

        for bank_balance in user_account.bank_balances:
            if bank_balance.balance != 0: 
                await track_bank(bank_balance.bank_index, is_writable=False)

        if writable_bank_index: 
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
        ix = await self.get_deposit_collateral_ix(
            amount,
            bank_index,
            user_token_account,
            user_id,
            reduce_only,
            user_initialized,
        )
        return await self.send_ix([ix])

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

    # async def deposit_collateral(
    #     self,
    #     amount: int,
    #     collateral_account_public_key: PublicKey,
    #     user_positions_account_public_key: Optional[PublicKey] = None,
    #     state: Optional[StateAccount] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_deposit_collateral_ix(
    #         amount,
    #         collateral_account_public_key,
    #         user_positions_account_public_key,
    #         state,
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def initialize_user_account_and_deposit_collateral(
    #     self,
    #     amount: int,
    #     collateral_account_public_key: PublicKey,
    #     state: Optional[StateAccount] = None,
    # ) -> tuple[TransactionSignature, PublicKey]:
    #     """Creates the Clearing House User account for a user, and deposits some initial collateral."""  # noqa: E501
    #     (
    #         user_positions_account,
    #         user_account_public_key,
    #         initialize_user_account_ix,
    #     ) = self.get_initialize_user_instructions()

    #     deposit_collateral_ix = await self.get_deposit_collateral_ix(
    #         amount,
    #         collateral_account_public_key,
    #         user_positions_account.public_key,
    #         state,
    #     )

    #     tx = Transaction().add(initialize_user_account_ix, deposit_collateral_ix)

    #     tx_sig = await self.program.provider.send(tx, [user_positions_account])

    #     return tx_sig, user_account_public_key

    # async def get_withdraw_collateral_ix(
    #     self,
    #     amount: int,
    #     collateral_account_public_key: PublicKey,
    #     user_account: Optional[User] = None,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user = (
    #         cast(
    #             User, await self.program.account["User"].fetch(user_account_public_key)
    #         )
    #         if user_account is None
    #         else user_account
    #     )
    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     return self.program.instruction["withdraw_collateral"](
    #         amount,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "collateral_vault": state.collateral_vault,
    #                 "collateral_vault_authority": state.collateral_vault_authority,
    #                 "insurance_vault": state.insurance_vault,
    #                 "insurance_vault_authority": state.insurance_vault_authority,
    #                 "user_collateral_account": collateral_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "token_program": TOKEN_PROGRAM_ID,
    #                 "markets": state.markets,
    #                 "user_positions": user.positions,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "deposit_history": state.deposit_history,
    #             },
    #         ),
    #     )

    # async def withdraw_collateral(
    #     self,
    #     amount: int,
    #     collateral_account_public_key: PublicKey,
    #     user: Optional[User] = None,
    #     state: Optional[StateAccount] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_withdraw_collateral_ix(
    #         amount, collateral_account_public_key, user, state
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def open_position(
    #     self,
    #     direction: PositionDirection,
    #     amount: int,
    #     market_index: int,
    #     limit_price: Optional[int] = None,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_open_position_ix(
    #         direction, amount, market_index, limit_price, discount_token, referrer
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_open_position_ix(
    #     self,
    #     direction: PositionDirection,
    #     amount: int,
    #     market_index: int,
    #     limit_price: Optional[int] = None,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    #     user_account: Optional[User] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user_account_to_use = (
    #         await self.get_user_account() if user_account is None else user_account
    #     )
    #     limit_price_to_use = 0 if limit_price is None else limit_price

    #     optional_accounts = {
    #         "discount_token": False,
    #         "referrer": False,
    #     }
    #     remaining_accounts = []
    #     if discount_token:
    #         optional_accounts["discount_token"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=discount_token,
    #                 is_writable=False,
    #                 is_signer=False,
    #             )
    #         )
    #     if referrer:
    #         optional_accounts["referrer"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=referrer,
    #                 is_writable=True,
    #                 is_signer=False,
    #             )
    #         )
    #     markets_account_to_use = (
    #         await self.get_markets_account()
    #         if markets_account is None
    #         else markets_account
    #     )
    #     price_oracle = markets_account_to_use.markets[market_index].amm.oracle
    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     return self.program.instruction["open_position"](
    #         direction,
    #         amount,
    #         market_index,
    #         limit_price_to_use,
    #         optional_accounts,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "markets": state.markets,
    #                 "user_positions": user_account_to_use.positions,
    #                 "trade_history": state.trade_history,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "funding_rate_history": state.funding_rate_history,
    #                 "oracle": price_oracle,
    #             },
    #             remaining_accounts=remaining_accounts,
    #         ),
    #     )

    # async def place_orders(
    #     self,
    #     order_params_list: list[OrderParams],
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    # ) -> TransactionSignature:
    #     tx = Transaction()
    #     for order_params in order_params_list:
    #         ix = await self.get_place_order_ix(order_params, discount_token, referrer)
    #         tx = tx.add(ix)
    #     return await self.program.provider.send(tx)

    # async def place_order(
    #     self,
    #     order_params: OrderParams,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_place_order_ix(order_params, discount_token, referrer)
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_place_order_ix(
    #     self,
    #     order_params: OrderParams,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    #     user_account: Optional[User] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    #     orders_state_account: Optional[OrderState] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user_account_to_use = (
    #         await self.get_user_account() if user_account is None else user_account
    #     )
    #     optional_accounts = {
    #         "discount_token": False,
    #         "referrer": False,
    #     }

    #     markets_account_to_use = (
    #         await self.get_markets_account()
    #         if markets_account is None
    #         else markets_account
    #     )
    #     price_oracle = markets_account_to_use.markets[
    #         order_params.market_index
    #     ].amm.oracle

    #     remaining_accounts = []
    #     if discount_token:
    #         optional_accounts["discount_token"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=discount_token,
    #                 is_writable=False,
    #                 is_signer=False,
    #             )
    #         )
    #     if referrer:
    #         optional_accounts["referrer"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=referrer,
    #                 is_writable=True,
    #                 is_signer=False,
    #             )
    #         )
    #     if order_params.oracle_price_offset != 0:
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=price_oracle,
    #                 is_writable=False,
    #                 is_signer=False,
    #             )
    #         )


    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )

    #     orders_state = (
    #         await self.get_orders_state_account()
    #         if orders_state_account is None
    #         else orders_state_account
    #     )

    #     return self.program.instruction["place_order"](
    #         order_params,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "markets": state.markets,
    #                 "user_orders": self.get_user_orders_public_key(),
    #                 "user_positions": user_account_to_use.positions,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "funding_rate_history": state.funding_rate_history,
    #                 "order_state": self.get_order_state_public_key(),
    #                 "order_history": orders_state.order_history,
    #                 "oracle": price_oracle,
    #             },
    #             remaining_accounts=remaining_accounts,
    #         ),
    #     )

    # async def place_and_fill_order(
    #     self,
    #     order_params: OrderParams,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_place_and_fill_order_ix(
    #         order_params, discount_token, referrer
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_place_and_fill_order_ix(
    #     self,
    #     order_params: OrderParams,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    #     user_account: Optional[User] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    #     orders_state_account: Optional[OrderState] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user_account_to_use = (
    #         await self.get_user_account() if user_account is None else user_account
    #     )
    #     optional_accounts = {
    #         "discount_token": False,
    #         "referrer": False,
    #     }
    #     remaining_accounts = []
    #     if discount_token:
    #         optional_accounts["discount_token"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=discount_token,
    #                 is_writable=False,
    #                 is_signer=False,
    #             )
    #         )
    #     if referrer:
    #         optional_accounts["referrer"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=referrer,
    #                 is_writable=True,
    #                 is_signer=False,
    #             )
    #         )

    #     markets_account_to_use = (
    #         await self.get_markets_account()
    #         if markets_account is None
    #         else markets_account
    #     )
    #     price_oracle = markets_account_to_use.markets[
    #         order_params.market_index
    #     ].amm.oracle

    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )

    #     orders_state = (
    #         await self.get_orders_state_account()
    #         if orders_state_account is None
    #         else orders_state_account
    #     )

    #     return self.program.instruction["place_and_fill_order"](
    #         order_params,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "markets": state.markets,
    #                 "user_orders": self.get_user_orders_public_key(),
    #                 "user_positions": user_account_to_use.positions,
    #                 "trade_history": state.trade_history,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "funding_rate_history": state.funding_rate_history,
    #                 "order_state": self.get_order_state_public_key(),
    #                 "order_history": orders_state.order_history,
    #                 "extended_curve_history": state.extended_curve_history,
    #                 "oracle": price_oracle,
    #             },
    #             remaining_accounts=remaining_accounts,
    #         ),
    #     )
        
    # async def cancel_all_orders(
    #     self,
    #     best_effort: bool,
    #     user_account: Optional[User] = None,
    #     state_account: Optional[StateAccount] = None,
    #     orders_state_account: Optional[OrderState] = None,
    # ) -> TransactionInstruction:
    #     ix = await self.get_cancel_all_orders_ix(
    #         best_effort,
    #         user_account,
    #         state_account,
    #         orders_state_account,
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)
    
    # async def get_cancel_all_orders_ix(
    #     self,
    #     best_effort: bool,
    #     user_account: Optional[User] = None,
    #     state_account: Optional[StateAccount] = None,
    #     orders_state_account: Optional[OrderState] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user_account_to_use = (
    #         await self.get_user_account() if user_account is None else user_account
    #     )
    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     orders_state = (
    #         await self.get_orders_state_account() if orders_state_account is None
    #         else orders_state_account
    #     )

    #     return self.program.instruction["cancel_all_orders"](
    #         best_effort,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "markets": state.markets,
    #                 "user_orders": self.get_user_orders_public_key(),
    #                 "user_positions": user_account_to_use.positions,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "funding_rate_history": state.funding_rate_history,
    #                 "order_state": self.get_order_state_public_key(),
    #                 "order_history": orders_state.order_history,
    #             }
    #         )
    #     )

    # async def cancel_order(
    #     self,
    #     order_id: int,
    #     oracle: PublicKey = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_cancel_order_ix(order_id, oracle)
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_cancel_order_ix(
    #     self,
    #     order_id: int,
    #     oracle: PublicKey = None,
    #     user_account: Optional[User] = None,
    #     state_account: Optional[StateAccount] = None,
    #     orders_state_account: Optional[OrderState] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user_account_to_use = (
    #         await self.get_user_account() if user_account is None else user_account
    #     )
    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     orders_state = (
    #         await self.get_orders_state_account()
    #         if orders_state_account is None
    #         else orders_state_account
    #     )
    #     remaining_accounts = []
    #     if oracle is not None:
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=oracle,
    #                 is_writable=False,
    #                 is_signer=False,
    #             )
    #         )

    #     return self.program.instruction["cancel_order"](
    #         order_id,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "markets": state.markets,
    #                 "user_orders": self.get_user_orders_public_key(),
    #                 "user_positions": user_account_to_use.positions,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "funding_rate_history": state.funding_rate_history,
    #                 "order_state": self.get_order_state_public_key(),
    #                 "order_history": orders_state.order_history,
    #             },
    #         remaining_accounts=remaining_accounts,

    #         ),
    #     )

    # async def get_close_position_ix(
    #     self,
    #     market_index: int,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    #     user_account: Optional[User] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user_account_to_use = (
    #         await self.get_user_account() if user_account is None else user_account
    #     )
    #     markets_account_to_use = (
    #         await self.get_markets_account()
    #         if markets_account is None
    #         else markets_account
    #     )
    #     price_oracle = markets_account_to_use.markets[market_index].amm.oracle

    #     optional_accounts = {
    #         "discount_token": False,
    #         "referrer": False,
    #     }
    #     remaining_accounts = []
    #     if discount_token is not None:
    #         optional_accounts["discount_token"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=discount_token,
    #                 is_writable=False,
    #                 is_signer=False,
    #             )
    #         )
    #     if referrer is not None:
    #         optional_accounts["referrer"] = True
    #         remaining_accounts.append(
    #             AccountMeta(
    #                 pubkey=referrer,
    #                 is_writable=True,
    #                 is_signer=False,
    #             )
    #         )

    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     return self.program.instruction["close_position"](
    #         market_index,
    #         optional_accounts,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "user": user_account_public_key,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "markets": state.markets,
    #                 "user_positions": user_account_to_use.positions,
    #                 "trade_history": state.trade_history,
    #                 "funding_payment_history": state.funding_payment_history,
    #                 "funding_rate_history": state.funding_rate_history,
    #                 "oracle": price_oracle,
    #             },
    #             remaining_accounts=remaining_accounts,
    #         ),
    #     )

    # async def close_position(
    #     self,
    #     market_index: int,
    #     discount_token: Optional[PublicKey] = None,
    #     referrer: Optional[PublicKey] = None,
    #     user_account: Optional[User] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionSignature:
    #     """Close an entire position. If you want to reduce a position, use the [open_position][driftpy.clearing_house.ClearingHouse.open_position] method in the opposite direction of the current position."""  # noqa: E501
    #     ix = await self.get_close_position_ix(
    #         market_index=market_index,
    #         discount_token=discount_token,
    #         referrer=referrer,
    #         user_account=user_account,
    #         markets_account=markets_account,
    #         state_account=state_account,
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def delete_user(self) -> TransactionSignature:
    #     user_account_public_key = self.get_user_account_public_key()
    #     user = await self.program.account["User"].fetch(user_account_public_key)
    #     return await self.program.rpc["DeleteUser"](
    #         ctx=Context(
    #             accounts={
    #                 "user": user_account_public_key,
    #                 "user_positions": user.positions,
    #                 "authority": self.program.provider.wallet.public_key,
    #             }
    #         )
    #     )

    # async def liquidate(
    #     self,
    #     liquidatee_user_account_public_key: PublicKey,
    #     liquidatee_user_account: Optional[User] = None,
    #     liquidatee_positions: Optional[UserPositions] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_liquidate_ix(
    #         liquidatee_user_account_public_key,
    #         liquidatee_user_account=liquidatee_user_account,
    #         liquidatee_positions=liquidatee_positions,
    #         markets_account=markets_account,
    #         state_account=state_account,
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_liquidate_ix(
    #     self,
    #     liquidatee_user_account_public_key: PublicKey,
    #     liquidatee_user_account: Optional[User] = None,
    #     liquidatee_positions: Optional[UserPositions] = None,
    #     markets_account: Optional[MarketsAccount] = None,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionInstruction:
    #     user_account_public_key = self.get_user_account_public_key()

    #     liquidatee_user_account_to_use = (
    #         cast(
    #             User,
    #             await self.program.account["User"].fetch(
    #                 liquidatee_user_account_public_key
    #             ),
    #         )
    #         if liquidatee_user_account is None
    #         else liquidatee_user_account
    #     )
    #     liquidatee_positions_to_use = (
    #         cast(
    #             UserPositions,
    #             await self.program.account["UserPositions"].fetch(
    #                 liquidatee_user_account_to_use.positions
    #             ),
    #         )
    #         if liquidatee_positions is None
    #         else liquidatee_positions
    #     )
    #     markets = (
    #         await self.get_markets_account()
    #         if markets_account is None
    #         else markets_account
    #     )

    #     remaining_accounts = []
    #     for position in liquidatee_positions_to_use.positions:
    #         if position.base_asset_amount != 0:
    #             market = markets.markets[position.market_index]
    #             remaining_accounts.append(
    #                 AccountMeta(
    #                     pubkey=market.amm.oracle,
    #                     is_writable=False,
    #                     is_signer=False,
    #                 )
    #             )

    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     return self.program.instruction["liquidate"](
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "authority": self.program.provider.wallet.public_key,
    #                 "user": liquidatee_user_account_public_key,
    #                 "liquidator": user_account_public_key,
    #                 "collateral_vault": state.collateral_vault,
    #                 "collateral_vault_authority": state.collateral_vault_authority,
    #                 "insurance_vault": state.insurance_vault,
    #                 "insurance_vault_authority": state.insurance_vault_authority,
    #                 "token_program": TOKEN_PROGRAM_ID,
    #                 "markets": state.markets,
    #                 "user_positions": liquidatee_user_account_to_use.positions,
    #                 "trade_history": state.trade_history,
    #                 "liquidation_history": state.liquidation_history,
    #                 "funding_payment_history": state.funding_payment_history,
    #             },
    #             remaining_accounts=remaining_accounts,
    #         )
    #     )

    # async def update_funding_rate(
    #     self,
    #     oracle: PublicKey,
    #     market_index: int,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_update_funding_rate_ix(oracle, market_index, state_account)
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_update_funding_rate_ix(
    #     self,
    #     oracle: PublicKey,
    #     market_index: int,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionInstruction:
    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     return self.program.instruction["update_funding_rate"](
    #         market_index,
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "markets": state.markets,
    #                 "oracle": oracle,
    #                 "funding_rate_history": state.funding_rate_history,
    #             },
    #         ),
    #     )

    # async def settle_funding_payment(
    #     self,
    #     user_account: PublicKey,
    #     user_positions_account: PublicKey,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionSignature:
    #     ix = await self.get_settle_funding_payment_ix(
    #         user_account, user_positions_account
    #     )
    #     tx = Transaction().add(ix)
    #     return await self.program.provider.send(tx)

    # async def get_settle_funding_payment_ix(
    #     self,
    #     user_account: PublicKey,
    #     user_positions_account: PublicKey,
    #     state_account: Optional[StateAccount] = None,
    # ) -> TransactionInstruction:
    #     state = (
    #         await self.get_state_account() if state_account is None else state_account
    #     )
    #     return self.program.instruction["settle_funding_payment"](
    #         ctx=Context(
    #             accounts={
    #                 "state": self.pdas.state,
    #                 "markets": state.markets,
    #                 "user": user_account,
    #                 "user_positions": user_positions_account,
    #                 "funding_payment_history": state.funding_payment_history,
    #             },
    #         )
    #     )