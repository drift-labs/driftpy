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
    get_user_account_public_key_and_nonce,
    get_user_orders_account_public_key_and_nonce,
    get_order_state_account_public_key_and_nonce,
)
from driftpy.types import (
    PositionDirection,
    StateAccount,
    MarketsAccount,
    Market,
    FundingPaymentHistoryAccount,
    FundingRateHistoryAccount,
    TradeHistoryAccount,
    LiquidationHistoryAccount,
    DepositHistoryAccount,
    ExtendedCurveHistoryAccount,
    User,
    UserPositions,
    OrderState,
    OrderHistoryAccount,
    OrderParams,
)

from driftpy.program import load_program


T = TypeVar("T", bound="ClearingHouse")


@dataclass
class ClearingHousePDAs:
    """A collection of pubkeys needed to instantiate
    [ClearingHouse][driftpy.clearing_house.ClearingHouse]"""

    state: PublicKey
    markets: PublicKey
    trade_history: PublicKey
    deposit_history: PublicKey
    funding_payment_history: PublicKey
    funding_rate_history: PublicKey
    liquidation_history: PublicKey
    curve_history: PublicKey
    extended_curve_history: PublicKey
    order_state: PublicKey


def get_clearing_house_state_account_public_key_and_nonce(
    program_id: PublicKey,
) -> tuple[PublicKey, int]:
    return PublicKey.find_program_address([b"clearing_house"], program_id)


async def _get_state_account(program: Program, state_pubkey: PublicKey) -> StateAccount:
    res = await program.account["State"].fetch(state_pubkey)
    return cast(StateAccount, res)


class ClearingHouse:
    """This class is the main way to interact with Drift Protocol.

    It allows you to subscribe to the various accounts where the Market's state is
    stored, as well as: opening positions, liquidating, settling funding, depositing &
    withdrawing, and more.

    The default way to construct a ClearingHouse instance is using the
    [create][driftpy.clearing_house.ClearingHouse.create] method.
    """

    def __init__(self, program: Program, pdas: ClearingHousePDAs):
        """Initialize the ClearingHouse object.

        Note: you probably want to use
        [create][driftpy.clearing_house.ClearingHouse.create]
        instead of this method.

        Args:
            program: The AnchorPy program object.
            pdas: The required PDAs for the ClearingHouse object.
        """
        self.program = program
        self.pdas = pdas
        self.user_account = None

    def _find_program_address(self, seeds: list[bytes]) -> tuple[PublicKey, int]:
        return PublicKey.find_program_address(seeds, self.program.program_id)

    async def get_state_account(self) -> StateAccount:
        res = await _get_state_account(self.program, self.pdas.state)
        return cast(StateAccount, res)

    async def get_markets_account(self) -> MarketsAccount:
        res = await self.program.account["Markets"].fetch(self.pdas.markets)
        return cast(MarketsAccount, res)

    async def get_market(self, market_index) -> Market:
        market = (await self.get_markets_account()).markets[market_index]
        return cast(Market, market)

    async def get_funding_payment_history_account(self) -> FundingPaymentHistoryAccount:
        res = await self.program.account["FundingPaymentHistory"].fetch(
            self.pdas.funding_payment_history
        )
        return cast(FundingPaymentHistoryAccount, res)

    async def get_funding_rate_history_account(self) -> FundingRateHistoryAccount:
        res = await self.program.account["FundingRateHistory"].fetch(
            self.pdas.funding_rate_history
        )
        return cast(FundingRateHistoryAccount, res)

    async def get_trade_history_account(self) -> TradeHistoryAccount:
        res = await self.program.account["TradeHistory"].fetch(self.pdas.trade_history)
        return cast(TradeHistoryAccount, res)

    async def get_liquidation_history_account(self) -> LiquidationHistoryAccount:
        res = await self.program.account["LiquidationHistory"].fetch(
            self.pdas.liquidation_history
        )
        return cast(LiquidationHistoryAccount, res)

    async def get_deposit_history_account(self) -> DepositHistoryAccount:
        res = await self.program.account["DepositHistory"].fetch(
            self.pdas.deposit_history
        )
        return cast(DepositHistoryAccount, res)

    async def get_curve_history_account(self) -> ExtendedCurveHistoryAccount:
        res = await self.program.account["CurveHistory"].fetch(self.pdas.curve_history)
        return cast(ExtendedCurveHistoryAccount, res)

    async def get_extended_curve_history_account(self) -> ExtendedCurveHistoryAccount:
        res = await self.program.account["ExtendedCurveHistory"].fetch(
            self.pdas.extended_curve_history
        )
        return cast(ExtendedCurveHistoryAccount, res)

    async def get_orders_state_account(self) -> OrderState:
        res = await self.program.account["OrderState"].fetch(self.pdas.order_state)
        return cast(OrderState, res)

    async def get_orders_history_account(self) -> OrderHistoryAccount:
        order_state = await self.get_orders_state_account()
        res = await self.program.account["OrderHistory"].fetch(
            order_state.order_history
        )
        return cast(OrderHistoryAccount, res)

    @staticmethod
    def _get_state_pubkey(program: Program) -> PublicKey:
        return PublicKey.find_program_address([b"clearing_house"], program.program_id)[
            0
        ]

    @classmethod
    async def create(cls: Type[T], program: Program) -> T:
        """Create a new `ClearingHouse` instance.

        Args:
            program: An AnchorPy Program instance.

        Returns:
            The new `ClearingHouse` instance.
        """
        state_pubkey = cls._get_state_pubkey(program)
        state = await _get_state_account(program, state_pubkey)
        pdas = ClearingHousePDAs(
            state=state_pubkey,
            markets=state.markets,
            trade_history=state.trade_history,
            deposit_history=state.deposit_history,
            funding_payment_history=state.funding_payment_history,
            funding_rate_history=state.funding_rate_history,
            liquidation_history=state.liquidation_history,
            curve_history=state.curve_history,
            extended_curve_history=state.extended_curve_history,
            order_state=state.order_state,
        )
        return cls(program, pdas)

    @classmethod
    async def create_from_env(cls: Type[T], env: str) -> T:
        """Create a new `ClearingHouse` instance.

        Args:
            program: An AnchorPy Program instance.

        Returns:
            The new `ClearingHouse` instance.
        """
        program = load_program(env)
        state_pubkey = cls._get_state_pubkey(program)
        state = await _get_state_account(program, state_pubkey)
        pdas = ClearingHousePDAs(
            state=state_pubkey,
            markets=state.markets,
            trade_history=state.trade_history,
            deposit_history=state.deposit_history,
            funding_payment_history=state.funding_payment_history,
            funding_rate_history=state.funding_rate_history,
            liquidation_history=state.liquidation_history,
            curve_history=state.curve_history,
            order_state=state.order_state,
            extended_curve_history=state.extended_curve_history,
        )
        return cls(program, pdas)

    def get_initialize_user_instructions(
        self,
    ) -> tuple[Keypair, PublicKey, TransactionInstruction]:
        user_public_key, user_account_nonce = get_user_account_public_key_and_nonce(
            self.program.program_id, self.program.provider.wallet.public_key
        )

        remaining_accounts: list[AccountMeta] = []
        optional_accounts = self.program.type["InitializeUserOptionalAccounts"](
            whitelist_token=False
        )

        user_positions = Keypair()
        initialize_user_account_ix = self.program.instruction["initialize_user"](
            user_account_nonce,
            optional_accounts,
            ctx=Context(
                accounts={
                    "user": user_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "rent": SYSVAR_RENT_PUBKEY,
                    "system_program": SYS_PROGRAM_ID,
                    "user_positions": user_positions.public_key,
                    "state": self.pdas.state,
                },
                remaining_accounts=remaining_accounts,
            ),
        )
        return user_positions, user_public_key, initialize_user_account_ix

    async def get_deposit_collateral_ix(
        self,
        amount: int,
        collateral_account_public_key: PublicKey,
        user_positions_account_public_key: Optional[PublicKey] = None,
        state: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        if user_positions_account_public_key is None:
            user_account = await self.get_user_account()
            user_positions_account_public_key = user_account.positions
        state_to_use = await self.get_state_account() if state is None else state
        return self.program.instruction["deposit_collateral"](
            amount,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "collateral_vault": state_to_use.collateral_vault,
                    "user_collateral_account": collateral_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "token_program": TOKEN_PROGRAM_ID,
                    "markets": state_to_use.markets,
                    "funding_payment_history": state_to_use.funding_payment_history,
                    "deposit_history": state_to_use.deposit_history,
                    "user_positions": user_positions_account_public_key,
                },
            ),
        )

    async def deposit_collateral(
        self,
        amount: int,
        collateral_account_public_key: PublicKey,
        user_positions_account_public_key: Optional[PublicKey] = None,
        state: Optional[StateAccount] = None,
    ) -> TransactionSignature:
        ix = await self.get_deposit_collateral_ix(
            amount,
            collateral_account_public_key,
            user_positions_account_public_key,
            state,
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def initialize_user_account_and_deposit_collateral(
        self,
        amount: int,
        collateral_account_public_key: PublicKey,
        state: Optional[StateAccount] = None,
    ) -> tuple[TransactionSignature, PublicKey]:
        """Creates the Clearing House User account for a user, and deposits some initial collateral."""  # noqa: E501
        (
            user_positions_account,
            user_account_public_key,
            initialize_user_account_ix,
        ) = self.get_initialize_user_instructions()

        deposit_collateral_ix = await self.get_deposit_collateral_ix(
            amount,
            collateral_account_public_key,
            user_positions_account.public_key,
            state,
        )

        tx = Transaction().add(initialize_user_account_ix, deposit_collateral_ix)

        tx_sig = await self.program.provider.send(tx, [user_positions_account])

        return tx_sig, user_account_public_key

    def get_user_account_public_key(self) -> PublicKey:
        """Get the address for the Clearing House User's account.

        NOT the user's wallet address.
        """
        return get_user_account_public_key_and_nonce(
            self.program.program_id, self.program.provider.wallet.public_key
        )[0]

    def get_user_orders_public_key(self) -> PublicKey:
        """Get the address for the Clearing House User's order account.

        NOT the user's wallet address.
        """
        return get_user_orders_account_public_key_and_nonce(
            self.program.program_id, self.program.provider.wallet.public_key
        )[0]

    def get_order_state_public_key(self) -> PublicKey:
        """Get the address for the Clearing House Order State account."""
        return get_order_state_account_public_key_and_nonce(self.program.program_id)[0]

    async def get_withdraw_collateral_ix(
        self,
        amount: int,
        collateral_account_public_key: PublicKey,
        user_account: Optional[User] = None,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        user = (
            cast(
                User, await self.program.account["User"].fetch(user_account_public_key)
            )
            if user_account is None
            else user_account
        )
        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        return self.program.instruction["withdraw_collateral"](
            amount,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "collateral_vault": state.collateral_vault,
                    "collateral_vault_authority": state.collateral_vault_authority,
                    "insurance_vault": state.insurance_vault,
                    "insurance_vault_authority": state.insurance_vault_authority,
                    "user_collateral_account": collateral_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "token_program": TOKEN_PROGRAM_ID,
                    "markets": state.markets,
                    "user_positions": user.positions,
                    "funding_payment_history": state.funding_payment_history,
                    "deposit_history": state.deposit_history,
                },
            ),
        )

    async def withdraw_collateral(
        self,
        amount: int,
        collateral_account_public_key: PublicKey,
        user: Optional[User] = None,
        state: Optional[StateAccount] = None,
    ) -> TransactionSignature:
        ix = await self.get_withdraw_collateral_ix(
            amount, collateral_account_public_key, user, state
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def open_position(
        self,
        direction: PositionDirection,
        amount: int,
        market_index: int,
        limit_price: Optional[int] = None,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
    ) -> TransactionSignature:
        ix = await self.get_open_position_ix(
            direction, amount, market_index, limit_price, discount_token, referrer
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_open_position_ix(
        self,
        direction: PositionDirection,
        amount: int,
        market_index: int,
        limit_price: Optional[int] = None,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
        user_account: Optional[User] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        user_account_to_use = (
            await self.get_user_account() if user_account is None else user_account
        )
        limit_price_to_use = 0 if limit_price is None else limit_price

        optional_accounts = {
            "discount_token": False,
            "referrer": False,
        }
        remaining_accounts = []
        if discount_token:
            optional_accounts["discount_token"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=discount_token,
                    is_writable=False,
                    is_signer=False,
                )
            )
        if referrer:
            optional_accounts["referrer"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=referrer,
                    is_writable=True,
                    is_signer=False,
                )
            )
        markets_account_to_use = (
            await self.get_markets_account()
            if markets_account is None
            else markets_account
        )
        price_oracle = markets_account_to_use.markets[market_index].amm.oracle
        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        return self.program.instruction["open_position"](
            direction,
            amount,
            market_index,
            limit_price_to_use,
            optional_accounts,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "markets": state.markets,
                    "user_positions": user_account_to_use.positions,
                    "trade_history": state.trade_history,
                    "funding_payment_history": state.funding_payment_history,
                    "funding_rate_history": state.funding_rate_history,
                    "oracle": price_oracle,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def place_orders(
        self,
        order_params_list: list[OrderParams],
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
    ) -> TransactionSignature:
        tx = Transaction()
        for order_params in order_params_list:
            ix = await self.get_place_order_ix(order_params, discount_token, referrer)
            tx = tx.add(ix)
        return await self.program.provider.send(tx)

    async def place_order(
        self,
        order_params: OrderParams,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
    ) -> TransactionSignature:
        ix = await self.get_place_order_ix(order_params, discount_token, referrer)
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_place_order_ix(
        self,
        order_params: OrderParams,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
        user_account: Optional[User] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
        orders_state_account: Optional[OrderState] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        user_account_to_use = (
            await self.get_user_account() if user_account is None else user_account
        )
        optional_accounts = {
            "discount_token": False,
            "referrer": False,
        }

        markets_account_to_use = (
            await self.get_markets_account()
            if markets_account is None
            else markets_account
        )
        price_oracle = markets_account_to_use.markets[
            order_params.market_index
        ].amm.oracle

        remaining_accounts = []
        if discount_token:
            optional_accounts["discount_token"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=discount_token,
                    is_writable=False,
                    is_signer=False,
                )
            )
        if referrer:
            optional_accounts["referrer"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=referrer,
                    is_writable=True,
                    is_signer=False,
                )
            )
        if order_params.oracle_price_offset != 0:
            remaining_accounts.append(
                AccountMeta(
                    pubkey=price_oracle,
                    is_writable=False,
                    is_signer=False,
                )
            )


        state = (
            await self.get_state_account() if state_account is None else state_account
        )

        orders_state = (
            await self.get_orders_state_account()
            if orders_state_account is None
            else orders_state_account
        )

        return self.program.instruction["place_order"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "markets": state.markets,
                    "user_orders": self.get_user_orders_public_key(),
                    "user_positions": user_account_to_use.positions,
                    "funding_payment_history": state.funding_payment_history,
                    "funding_rate_history": state.funding_rate_history,
                    "order_state": self.get_order_state_public_key(),
                    "order_history": orders_state.order_history,
                    "oracle": price_oracle,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def place_and_fill_order(
        self,
        order_params: OrderParams,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
    ) -> TransactionSignature:
        ix = await self.get_place_and_fill_order_ix(
            order_params, discount_token, referrer
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_place_and_fill_order_ix(
        self,
        order_params: OrderParams,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
        user_account: Optional[User] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
        orders_state_account: Optional[OrderState] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        user_account_to_use = (
            await self.get_user_account() if user_account is None else user_account
        )
        optional_accounts = {
            "discount_token": False,
            "referrer": False,
        }
        remaining_accounts = []
        if discount_token:
            optional_accounts["discount_token"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=discount_token,
                    is_writable=False,
                    is_signer=False,
                )
            )
        if referrer:
            optional_accounts["referrer"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=referrer,
                    is_writable=True,
                    is_signer=False,
                )
            )

        markets_account_to_use = (
            await self.get_markets_account()
            if markets_account is None
            else markets_account
        )
        price_oracle = markets_account_to_use.markets[
            order_params.market_index
        ].amm.oracle

        state = (
            await self.get_state_account() if state_account is None else state_account
        )

        orders_state = (
            await self.get_orders_state_account()
            if orders_state_account is None
            else orders_state_account
        )

        return self.program.instruction["place_and_fill_order"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "markets": state.markets,
                    "user_orders": self.get_user_orders_public_key(),
                    "user_positions": user_account_to_use.positions,
                    "trade_history": state.trade_history,
                    "funding_payment_history": state.funding_payment_history,
                    "funding_rate_history": state.funding_rate_history,
                    "order_state": self.get_order_state_public_key(),
                    "order_history": orders_state.order_history,
                    "extended_curve_history": state.extended_curve_history,
                    "oracle": price_oracle,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def cancel_order(
        self,
        order_id: int,
        oracle: PublicKey = None,
    ) -> TransactionSignature:
        ix = await self.get_cancel_order_ix(order_id, oracle)
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_cancel_order_ix(
        self,
        order_id: int,
        oracle: PublicKey = None,
        user_account: Optional[User] = None,
        state_account: Optional[StateAccount] = None,
        orders_state_account: Optional[OrderState] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        user_account_to_use = (
            await self.get_user_account() if user_account is None else user_account
        )
        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        orders_state = (
            await self.get_orders_state_account()
            if orders_state_account is None
            else orders_state_account
        )
        remaining_accounts = []
        if oracle is not None:
            remaining_accounts.append(
                AccountMeta(
                    pubkey=oracle,
                    is_writable=False,
                    is_signer=False,
                )
            )

        return self.program.instruction["cancel_order"](
            order_id,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "markets": state.markets,
                    "user_orders": self.get_user_orders_public_key(),
                    "user_positions": user_account_to_use.positions,
                    "funding_payment_history": state.funding_payment_history,
                    "funding_rate_history": state.funding_rate_history,
                    "order_state": self.get_order_state_public_key(),
                    "order_history": orders_state.order_history,
                },
            remaining_accounts=remaining_accounts,

            ),
        )

    async def get_user_account(self) -> User:
        if self.user_account is not None:
            return self.user_account

        user_account_pubkey = self.get_user_account_public_key()
        self.user_account = cast(User, await self.program.account["User"].fetch(user_account_pubkey))
        return self.user_account

    async def get_close_position_ix(
        self,
        market_index: int,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
        user_account: Optional[User] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()
        user_account_to_use = (
            await self.get_user_account() if user_account is None else user_account
        )
        markets_account_to_use = (
            await self.get_markets_account()
            if markets_account is None
            else markets_account
        )
        price_oracle = markets_account_to_use.markets[market_index].amm.oracle

        optional_accounts = {
            "discount_token": False,
            "referrer": False,
        }
        remaining_accounts = []
        if discount_token is not None:
            optional_accounts["discount_token"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=discount_token,
                    is_writable=False,
                    is_signer=False,
                )
            )
        if referrer is not None:
            optional_accounts["referrer"] = True
            remaining_accounts.append(
                AccountMeta(
                    pubkey=referrer,
                    is_writable=True,
                    is_signer=False,
                )
            )

        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        return self.program.instruction["close_position"](
            market_index,
            optional_accounts,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "user": user_account_public_key,
                    "authority": self.program.provider.wallet.public_key,
                    "markets": state.markets,
                    "user_positions": user_account_to_use.positions,
                    "trade_history": state.trade_history,
                    "funding_payment_history": state.funding_payment_history,
                    "funding_rate_history": state.funding_rate_history,
                    "oracle": price_oracle,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def close_position(
        self,
        market_index: int,
        discount_token: Optional[PublicKey] = None,
        referrer: Optional[PublicKey] = None,
        user_account: Optional[User] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionSignature:
        """Close an entire position. If you want to reduce a position, use the [open_position][driftpy.clearing_house.ClearingHouse.open_position] method in the opposite direction of the current position."""  # noqa: E501
        ix = await self.get_close_position_ix(
            market_index=market_index,
            discount_token=discount_token,
            referrer=referrer,
            user_account=user_account,
            markets_account=markets_account,
            state_account=state_account,
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def delete_user(self) -> TransactionSignature:
        user_account_public_key = self.get_user_account_public_key()
        user = await self.program.account["User"].fetch(user_account_public_key)
        return await self.program.rpc["DeleteUser"](
            ctx=Context(
                accounts={
                    "user": user_account_public_key,
                    "user_positions": user.positions,
                    "authority": self.program.provider.wallet.public_key,
                }
            )
        )

    async def liquidate(
        self,
        liquidatee_user_account_public_key: PublicKey,
        liquidatee_user_account: Optional[User] = None,
        liquidatee_positions: Optional[UserPositions] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionSignature:
        ix = await self.get_liquidate_ix(
            liquidatee_user_account_public_key,
            liquidatee_user_account=liquidatee_user_account,
            liquidatee_positions=liquidatee_positions,
            markets_account=markets_account,
            state_account=state_account,
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_liquidate_ix(
        self,
        liquidatee_user_account_public_key: PublicKey,
        liquidatee_user_account: Optional[User] = None,
        liquidatee_positions: Optional[UserPositions] = None,
        markets_account: Optional[MarketsAccount] = None,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        user_account_public_key = self.get_user_account_public_key()

        liquidatee_user_account_to_use = (
            cast(
                User,
                await self.program.account["User"].fetch(
                    liquidatee_user_account_public_key
                ),
            )
            if liquidatee_user_account is None
            else liquidatee_user_account
        )
        liquidatee_positions_to_use = (
            cast(
                UserPositions,
                await self.program.account["UserPositions"].fetch(
                    liquidatee_user_account_to_use.positions
                ),
            )
            if liquidatee_positions is None
            else liquidatee_positions
        )
        markets = (
            await self.get_markets_account()
            if markets_account is None
            else markets_account
        )

        remaining_accounts = []
        for position in liquidatee_positions_to_use.positions:
            if position.base_asset_amount != 0:
                market = markets.markets[position.market_index]
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=market.amm.oracle,
                        is_writable=False,
                        is_signer=False,
                    )
                )

        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        return self.program.instruction["liquidate"](
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "authority": self.program.provider.wallet.public_key,
                    "user": liquidatee_user_account_public_key,
                    "liquidator": user_account_public_key,
                    "collateral_vault": state.collateral_vault,
                    "collateral_vault_authority": state.collateral_vault_authority,
                    "insurance_vault": state.insurance_vault,
                    "insurance_vault_authority": state.insurance_vault_authority,
                    "token_program": TOKEN_PROGRAM_ID,
                    "markets": state.markets,
                    "user_positions": liquidatee_user_account_to_use.positions,
                    "trade_history": state.trade_history,
                    "liquidation_history": state.liquidation_history,
                    "funding_payment_history": state.funding_payment_history,
                },
                remaining_accounts=remaining_accounts,
            )
        )

    async def update_funding_rate(
        self,
        oracle: PublicKey,
        market_index: int,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionSignature:
        ix = await self.get_update_funding_rate_ix(oracle, market_index, state_account)
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_update_funding_rate_ix(
        self,
        oracle: PublicKey,
        market_index: int,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        return self.program.instruction["update_funding_rate"](
            market_index,
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "markets": state.markets,
                    "oracle": oracle,
                    "funding_rate_history": state.funding_rate_history,
                },
            ),
        )

    async def settle_funding_payment(
        self,
        user_account: PublicKey,
        user_positions_account: PublicKey,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionSignature:
        ix = await self.get_settle_funding_payment_ix(
            user_account, user_positions_account
        )
        tx = Transaction().add(ix)
        return await self.program.provider.send(tx)

    async def get_settle_funding_payment_ix(
        self,
        user_account: PublicKey,
        user_positions_account: PublicKey,
        state_account: Optional[StateAccount] = None,
    ) -> TransactionInstruction:
        state = (
            await self.get_state_account() if state_account is None else state_account
        )
        return self.program.instruction["settle_funding_payment"](
            ctx=Context(
                accounts={
                    "state": self.pdas.state,
                    "markets": state.markets,
                    "user": user_account,
                    "user_positions": user_positions_account,
                    "funding_payment_history": state.funding_payment_history,
                },
            )
        )

    @staticmethod
    def local_idl() -> Idl:
        """Load the `clearing_house` IDL embedded in the Python package."""
        with resources.open_text("driftpy.idl", "clearing_house.json") as f:
            idl_raw = json.load(f)
        return Idl.from_json(idl_raw)
