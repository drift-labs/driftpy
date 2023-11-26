from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.transaction import Transaction
from solders.transaction import VersionedTransaction
from solders.transaction import TransactionVersion, Legacy
from solders.message import MessageV0
from solders.instruction import Instruction
from solders.system_program import ID
from solders.sysvar import RENT
from solders.address_lookup_table_account import AddressLookupTableAccount
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Processed
from solana.transaction import AccountMeta
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from spl.token.constants import TOKEN_PROGRAM_ID
from anchorpy import Program, Context, Idl, Provider, Wallet
from struct import pack_into
from pathlib import Path

import driftpy
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.address_lookup_table import get_address_lookup_table
from driftpy.constants.numeric_constants import (
    QUOTE_SPOT_MARKET_INDEX,
)
from driftpy.drift_user import DriftUser
from driftpy.accounts import *

from driftpy.constants.config import DriftEnv, DRIFT_PROGRAM_ID, configs

from typing import Union, Optional, List
from driftpy.math.positions import is_available, is_spot_position_available

DEFAULT_USER_NAME = "Main Account"

DEFAULT_TX_OPTIONS = TxOpts(skip_confirmation=False, preflight_commitment=Processed)


class DriftClient:
    """This class is the main way to interact with Drift Protocol including
    depositing, opening new positions, closing positions, placing orders, etc.
    """

    def __init__(
        self,
        connection: AsyncClient,
        wallet: Union[Keypair, Wallet],
        env: DriftEnv = "mainnet",
        program_id: Optional[Pubkey] = DRIFT_PROGRAM_ID,
        opts: TxOpts = DEFAULT_TX_OPTIONS,
        authority: Pubkey = None,
        account_subscription: Optional[
            AccountSubscriptionConfig
        ] = AccountSubscriptionConfig.default(),
        tx_params: Optional[TxParams] = None,
        tx_version: Optional[TransactionVersion] = None,
        active_sub_account_id: Optional[int] = None,
        sub_account_ids: Optional[list[int]] = None,
        market_lookup_table: Optional[Pubkey] = None,
    ):
        """Initializes the drift client object -- likely want to use the .from_config method instead of this one

        Args:
            program (Program): Drift anchor program (see from_config on how to initialize it)
            authority (Keypair, optional): Authority of all txs - if None will default to the Anchor Provider.Wallet Keypair.
        """
        self.connection = connection

        file = Path(str(driftpy.__path__[0]) + "/idl/drift.json")
        with file.open() as f:
            raw = file.read_text()
        idl = Idl.from_json(raw)

        provider = Provider(connection, wallet, opts)
        self.program_id = program_id
        self.program = Program(
            idl,
            self.program_id,
            provider,
        )

        if isinstance(wallet, Keypair):
            wallet = Wallet(wallet)

        if authority is None:
            authority = wallet.public_key

        self.wallet = wallet
        self.authority = authority
        self.usdc_ata = None
        self.spot_market_atas = {}

        self.active_sub_account_id = (
            active_sub_account_id if active_sub_account_id is not None else 0
        )
        self.sub_account_ids = (
            sub_account_ids
            if sub_account_ids is not None
            else [self.active_sub_account_id]
        )
        self.users = {}

        self.account_subscriber = account_subscription.get_drift_client_subscriber(
            self.program
        )
        self.account_subscription_config = account_subscription

        self.market_lookup_table = (
            market_lookup_table
            if market_lookup_table is not None
            else configs[env].market_lookup_table
        )
        self.market_lookup_table_account: Optional[AddressLookupTableAccount] = None

        if tx_params is None:
            tx_params = TxParams(600_000, 0)

        self.tx_params = tx_params

        self.tx_version = tx_version if tx_version is not None else Legacy

    async def subscribe(self):
        await self.account_subscriber.subscribe()
        for sub_account_id in self.sub_account_ids:
            await self.add_user(sub_account_id)

    async def add_user(self, sub_account_id: int):
        if sub_account_id in self.users:
            return

        user = DriftUser(
            drift_client=self,
            authority=self.authority,
            sub_account_id=sub_account_id,
            account_subscription=self.account_subscription_config,
        )
        await user.subscribe()
        self.users[sub_account_id] = user

    def unsubscribe(self):
        self.account_subscriber.unsubscribe()

    def get_user_account_public_key(self, sub_account_id=0) -> Pubkey:
        return get_user_account_public_key(
            self.program_id, self.authority, sub_account_id
        )

    def get_user(self, sub_account_id=0) -> DriftUser:
        if sub_account_id not in self.users:
            raise KeyError(f"No sub account id {sub_account_id} found")

        return self.users[sub_account_id]

    async def get_user_account(self, sub_account_id=0) -> UserAccount:
        return await self.get_user(sub_account_id).get_user_account()

    def switch_active_user(self, sub_account_id: int):
        self.active_sub_account_id = sub_account_id

    def get_state_public_key(self):
        return get_state_public_key(self.program_id)

    def get_user_stats_public_key(self):
        return get_user_stats_account_public_key(self.program_id, self.authority)

    async def get_state_account(self) -> Optional[StateAccount]:
        state_and_slot = await self.account_subscriber.get_state_account_and_slot()
        return getattr(state_and_slot, "data", None)

    async def get_perp_market_account(
        self, market_index: int
    ) -> Optional[PerpMarketAccount]:
        perp_market_and_slot = await self.account_subscriber.get_perp_market_and_slot(
            market_index
        )
        return getattr(perp_market_and_slot, "data", None)

    async def get_spot_market_account(
        self, market_index: int
    ) -> Optional[SpotMarketAccount]:
        spot_market_and_slot = await self.account_subscriber.get_spot_market_and_slot(
            market_index
        )
        return getattr(spot_market_and_slot, "data", None)

    async def get_oracle_price_data(self, oracle: Pubkey) -> Optional[OraclePriceData]:
        oracle_price_data_and_slot = (
            await self.account_subscriber.get_oracle_data_and_slot(oracle)
        )
        return getattr(oracle_price_data_and_slot, "data", None)

    async def get_oracle_price_data_for_perp_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        oracle = (await self.get_perp_market_account(market_index)).amm.oracle
        return await self.get_oracle_price_data(oracle)

    async def get_oracle_price_data_for_spot_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        oracle = (await self.get_spot_market_account(market_index)).oracle
        return await self.get_oracle_price_data(oracle)

    async def fetch_market_lookup_table(self) -> AddressLookupTableAccount:
        if self.market_lookup_table_account is not None:
            return self.market_lookup_table_account

        self.market_lookup_table_account = await get_address_lookup_table(
            self.connection, self.market_lookup_table
        )
        return self.market_lookup_table_account

    async def send_ixs(
        self,
        ixs: Union[Instruction, list[Instruction]],
        signers=None,
        lookup_tables: list[AddressLookupTableAccount] = None,
    ):
        if isinstance(ixs, Instruction):
            ixs = [ixs]

        if self.tx_params.compute_units is not None:
            ixs.insert(0, set_compute_unit_limit(self.tx_params.compute_units))

        if self.tx_params.compute_units_price is not None:
            ixs.insert(1, set_compute_unit_price(self.tx_params.compute_units_price))

        latest_blockhash = (
            await self.program.provider.connection.get_latest_blockhash()
        ).value.blockhash

        if self.tx_version == Legacy:
            tx = Transaction(
                instructions=ixs,
                recent_blockhash=latest_blockhash,
                fee_payer=self.wallet.public_key,
            )

            tx.sign_partial(self.wallet.payer)

            if signers is not None:
                [tx.sign_partial(signer) for signer in signers]
        elif self.tx_version == 0:
            if lookup_tables is None:
                lookup_tables = [await self.fetch_market_lookup_table()]
            msg = MessageV0.try_compile(
                self.wallet.public_key, ixs, lookup_tables, latest_blockhash
            )
            tx = VersionedTransaction(msg, [self.wallet.payer])
        else:
            raise NotImplementedError("unknown tx version", self.tx_version)

        return await self.program.provider.send(tx)

    async def initialize_user(self, sub_account_id: int = 0, name: str = None):
        """intializes a drift user

        Args:
            sub_account_id (int, optional): subaccount id to initialize. Defaults to 0.

        Returns:
            str: tx signature
        """
        ixs = []
        if sub_account_id == 0:
            ixs.append(self.get_initialize_user_stats())
            if name is None:
                name = DEFAULT_USER_NAME

        if name is None:
            name = "Subaccount " + str(sub_account_id + 1)

        ix = self.get_initialize_user_instructions(sub_account_id, name)
        ixs.append(ix)
        return await self.send_ixs(ixs)

    def get_initialize_user_stats(
        self,
    ):
        state_public_key = self.get_state_public_key()
        user_stats_public_key = self.get_user_stats_public_key()

        return self.program.instruction["initialize_user_stats"](
            ctx=Context(
                accounts={
                    "user_stats": user_stats_public_key,
                    "state": state_public_key,
                    "authority": self.authority,
                    "payer": self.authority,
                    "rent": RENT,
                    "system_program": ID,
                },
            ),
        )

    def get_initialize_user_instructions(
        self, sub_account_id: int = 0, name: str = DEFAULT_USER_NAME
    ) -> Instruction:
        user_public_key = self.get_user_account_public_key(sub_account_id)
        state_public_key = self.get_state_public_key()
        user_stats_public_key = self.get_user_stats_public_key()

        if len(name) > 32:
            raise Exception("name too long")

        name_bytes = bytearray(32)
        pack_into(f"{len(name)}s", name_bytes, 0, name.encode("utf-8"))
        offset = len(name)
        for _ in range(32 - len(name)):
            pack_into("1s", name_bytes, offset, " ".encode("utf-8"))
            offset += 1

        str_name_bytes = name_bytes.hex()
        name_byte_array = []
        for i in range(0, len(str_name_bytes), 2):
            name_byte_array.append(int(str_name_bytes[i : i + 2], 16))

        initialize_user_account_ix = self.program.instruction["initialize_user"](
            sub_account_id,
            name_byte_array,
            ctx=Context(
                accounts={
                    "user": user_public_key,
                    "user_stats": user_stats_public_key,
                    "state": state_public_key,
                    "authority": self.authority,
                    "payer": self.authority,
                    "rent": RENT,
                    "system_program": ID,
                },
            ),
        )
        return initialize_user_account_ix

    async def get_remaining_accounts(
        self,
        user_accounts: list[UserAccount] = (),
        writable_perp_market_indexes: list[int] = (),
        writable_spot_market_indexes: list[int] = (),
        readable_spot_market_indexes: list[int] = (),
        readable_perp_market_indexes: list[int] = (),
    ):
        (
            oracle_map,
            spot_market_map,
            perp_market_map,
        ) = await self.get_remaining_accounts_for_users(user_accounts)

        for perp_market_index in readable_perp_market_indexes:
            await self.add_perp_market_to_remaining_account_maps(
                perp_market_index, False, oracle_map, spot_market_map, perp_market_map
            )

        for spot_market_index in readable_spot_market_indexes:
            await self.add_spot_market_to_remaining_account_maps(
                spot_market_index, False, oracle_map, spot_market_map
            )

        for perp_market_index in writable_perp_market_indexes:
            await self.add_perp_market_to_remaining_account_maps(
                perp_market_index, True, oracle_map, spot_market_map, perp_market_map
            )

        for spot_market_index in writable_spot_market_indexes:
            await self.add_spot_market_to_remaining_account_maps(
                spot_market_index, True, oracle_map, spot_market_map
            )

        remaining_accounts = [
            *oracle_map.values(),
            *spot_market_map.values(),
            *perp_market_map.values(),
        ]

        return remaining_accounts

    async def add_perp_market_to_remaining_account_maps(
        self,
        market_index: int,
        writable: bool,
        oracle_account_map: dict[str, AccountMeta],
        spot_market_account_map: dict[int, AccountMeta],
        perp_market_account_map: dict[int, AccountMeta],
    ) -> None:
        perp_market_account = await self.get_perp_market_account(market_index)

        perp_market_account_map[market_index] = AccountMeta(
            pubkey=perp_market_account.pubkey, is_signer=False, is_writable=writable
        )

        oracle_account_map[str(perp_market_account.amm.oracle)] = AccountMeta(
            pubkey=perp_market_account.amm.oracle, is_signer=False, is_writable=False
        )

        await self.add_spot_market_to_remaining_account_maps(
            perp_market_account.quote_spot_market_index,
            False,
            oracle_account_map,
            spot_market_account_map,
        )

    async def add_spot_market_to_remaining_account_maps(
        self,
        market_index: int,
        writable: bool,
        oracle_account_map: dict[str, AccountMeta],
        spot_market_account_map: dict[int, AccountMeta],
    ) -> None:
        spot_market_account = await self.get_spot_market_account(market_index)

        spot_market_account_map[market_index] = AccountMeta(
            pubkey=spot_market_account.pubkey, is_signer=False, is_writable=writable
        )

        if spot_market_account.oracle != Pubkey.default():
            oracle_account_map[str(spot_market_account.oracle)] = AccountMeta(
                pubkey=spot_market_account.oracle, is_signer=False, is_writable=False
            )

    async def get_remaining_accounts_for_users(
        self, user_accounts: list[UserAccount]
    ) -> (dict[str, AccountMeta], dict[int, AccountMeta], dict[int, AccountMeta]):
        oracle_map = {}
        spot_market_map = {}
        perp_market_map = {}

        for user_account in user_accounts:
            for spot_position in user_account.spot_positions:
                if not is_spot_position_available(spot_position):
                    await self.add_spot_market_to_remaining_account_maps(
                        spot_position.market_index, False, oracle_map, spot_market_map
                    )

                if spot_position.open_asks != 0 or spot_position.open_bids != 0:
                    await self.add_spot_market_to_remaining_account_maps(
                        QUOTE_SPOT_MARKET_INDEX, False, oracle_map, spot_market_map
                    )

            for position in user_account.perp_positions:
                if not is_available(position):
                    await self.add_perp_market_to_remaining_account_maps(
                        position.market_index,
                        False,
                        oracle_map,
                        spot_market_map,
                        perp_market_map,
                    )

        return oracle_map, spot_market_map, perp_market_map

    async def withdraw(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey,
        reduce_only: bool = False,
        sub_account_id: int = 0,
    ):
        """withdraws from drift protocol (can also allow borrowing)

        Args:
            amount (int): amount to withdraw
            spot_market_index (int):
            user_token_account (Pubkey): ata of the account to withdraw to
            reduce_only (bool, optional): if True will only withdraw existing funds else if False will allow taking out borrows. Defaults to False.
            sub_account_id (int, optional): subaccount. Defaults to 0.

        Returns:
            str: tx sig
        """
        return await self.send_ixs(
            [
                await self.get_withdraw_collateral_ix(
                    amount,
                    spot_market_index,
                    user_token_account,
                    reduce_only,
                    sub_account_id,
                )
            ]
        )

    async def get_withdraw_collateral_ix(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey,
        reduce_only: bool = False,
        sub_account_id: int = 0,
    ):
        spot_market = await self.get_spot_market_account(spot_market_index)
        remaining_accounts = await self.get_remaining_accounts(
            user_accounts=[await self.get_user_account(sub_account_id)],
            writable_spot_market_indexes=[spot_market_index],
        )
        dc_signer = get_drift_client_signer_public_key(self.program_id)

        return self.program.instruction["withdraw"](
            spot_market_index,
            amount,
            reduce_only,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "spot_market": spot_market.pubkey,
                    "spot_market_vault": spot_market.vault,
                    "drift_signer": dc_signer,
                    "user": self.get_user_account_public_key(sub_account_id),
                    "user_stats": self.get_user_stats_public_key(),
                    "user_token_account": user_token_account,
                    "authority": self.authority,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def deposit(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey,
        sub_account_id: int = 0,
        reduce_only=False,
        user_initialized=True,
    ):
        """deposits collateral into protocol

        Args:
            amount (int): amount to deposit
            spot_market_index (int):
            user_token_account (Pubkey):
            sub_account_id (int, optional): subaccount to deposit into. Defaults to 0.
            reduce_only (bool, optional): paying back borrow vs depositing new assets. Defaults to False.
            user_initialized (bool, optional): if need to initialize user account too set this to False. Defaults to True.

        Returns:
            str: sig
        """
        return await self.send_ixs(
            [
                await self.get_deposit_collateral_ix(
                    amount,
                    spot_market_index,
                    user_token_account,
                    sub_account_id,
                    reduce_only,
                    user_initialized,
                )
            ]
        )

    async def get_deposit_collateral_ix(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey,
        sub_account_id: int = 0,
        reduce_only=False,
        user_initialized=True,
    ) -> Instruction:
        if user_initialized:
            remaining_accounts = await self.get_remaining_accounts(
                writable_spot_market_indexes=[spot_market_index],
                user_accounts=[await self.get_user_account(sub_account_id)],
            )
        else:
            raise Exception("not implemented...")

        spot_market_pk = get_spot_market_public_key(self.program_id, spot_market_index)
        spot_vault_public_key = get_spot_market_vault_public_key(
            self.program_id, spot_market_index
        )
        user_account_public_key = get_user_account_public_key(
            self.program_id, self.authority, sub_account_id
        )
        return self.program.instruction["deposit"](
            spot_market_index,
            amount,
            reduce_only,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "spot_market": spot_market_pk,
                    "spot_market_vault": spot_vault_public_key,
                    "user": user_account_public_key,
                    "user_stats": self.get_user_stats_public_key(),
                    "user_token_account": user_token_account,
                    "authority": self.authority,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def add_liquidity(
        self, amount: int, market_index: int, sub_account_id: int = 0
    ):
        """mint LP tokens and add liquidity to the DAMM

        Args:
            amount (int): amount of lp tokens to mint
            market_index (int): market you want to lp in
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            str: tx sig
        """
        return await self.send_ixs(
            [await self.get_add_liquidity_ix(amount, market_index, sub_account_id)]
        )

    async def get_add_liquidity_ix(
        self, amount: int, market_index: int, sub_account_id: int = 0
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[await self.get_user_account(sub_account_id)],
        )
        user_account_public_key = get_user_account_public_key(
            self.program_id, self.authority, sub_account_id
        )

        return self.program.instruction["add_perp_lp_shares"](
            amount,
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def remove_liquidity(
        self, amount: int, market_index: int, sub_account_id: int = 0
    ):
        """burns LP tokens and removes liquidity to the DAMM

        Args:
            amount (int): amount of lp tokens to burn
            market_index (int):
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            str: tx sig
        """
        return await self.send_ixs(
            [await self.get_remove_liquidity_ix(amount, market_index, sub_account_id)]
        )

    async def get_remove_liquidity_ix(
        self, amount: int, market_index: int, sub_account_id: int = 0
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[await self.get_user_account(sub_account_id)],
        )
        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        return self.program.instruction["remove_perp_lp_shares"](
            amount,
            market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "user": user_account_public_key,
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def cancel_orders(self, sub_account_id: int = 0):
        """cancel all existing orders on the book

        Args:
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            str: tx sig
        """
        return await self.send_ixs(await self.get_cancel_orders_ix(sub_account_id))

    async def get_cancel_orders_ix(self, sub_account_id: int = 0):
        remaining_accounts = await self.get_remaining_accounts(
            user_accounts=[await self.get_user_account(sub_account_id)]
        )

        return self.program.instruction["cancel_orders"](
            None,
            None,
            None,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def cancel_order(
        self,
        order_id: Optional[int] = None,
        sub_account_id: int = 0,
    ):
        """cancel specific order (if order_id=None will be most recent order)

        Args:
            order_id (Optional[int], optional): Defaults to None.
            sub_account_id (int, optional): subaccount id which contains order. Defaults to 0.

        Returns:
            str: tx sig
        """
        return await self.send_ixs(
            await self.get_cancel_order_ix(order_id, sub_account_id),
        )

    async def get_cancel_order_ix(
        self, order_id: Optional[int] = None, sub_account_id: int = 0
    ):
        remaining_accounts = await self.get_remaining_accounts(
            user_accounts=[await self.get_user_account(sub_account_id)]
        )

        return self.program.instruction["cancel_order"](
            order_id,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def open_position(
        self,
        direction: PositionDirection,
        amount: int,
        market_index: int,
        sub_account_id: int = 0,
        limit_price: int = 0,
        ioc: bool = False,
    ):
        return await self.send_ixs(
            await self.get_open_position_ix(
                direction,
                amount,
                market_index,
                sub_account_id,
                limit_price,
                ioc,
            ),
        )

    async def get_open_position_ix(
        self,
        direction: PositionDirection,
        amount: int,
        market_index: int,
        sub_account_id: int = 0,
        limit_price: int = 0,
        ioc: bool = False,
    ):
        order = self.default_order_params(
            order_type=OrderType.MARKET(),
            direction=direction,
            market_index=market_index,
            base_asset_amount=amount,
        )
        order.limit_price = limit_price

        ix = await self.get_place_and_take_ix(order, sub_account_id=sub_account_id)
        return ix

    def get_increase_compute_ix(self) -> Instruction:
        program_id = Pubkey("ComputeBudget111111111111111111111111111111")

        name_bytes = bytearray(1 + 4 + 4)
        pack_into("B", name_bytes, 0, 0)
        pack_into("I", name_bytes, 1, 500_000)
        pack_into("I", name_bytes, 5, 0)
        data = bytes(name_bytes)

        compute_ix = Instruction(program_id, data, [])

        return compute_ix

    async def place_spot_order(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
        sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                self.get_increase_compute_ix(),
                await self.get_place_spot_order_ix(order_params, sub_account_id),
            ]
        )

    async def get_place_spot_order_ix(
        self,
        order_params: OrderParams,
        sub_account_id: int = 0,
    ):
        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            readable_spot_market_indexes=[
                QUOTE_SPOT_MARKET_INDEX,
                order_params.market_index,
            ],
            user_accounts=[await self.get_user_account(sub_account_id)],
        )

        ix = self.program.instruction["place_spot_order"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "authority": self.wallet.public_key,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return ix

    async def get_place_spot_orders_ix(
        self,
        order_params: List[OrderParams],
        sub_account_id: int = 0,
    ):
        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            readable_spot_market_indexes=[
                QUOTE_SPOT_MARKET_INDEX,
                order_params.market_index,
            ],
            user_accounts=[await self.get_user_account(sub_account_id)],
        )

        ixs = [
            self.program.instruction["cancel_orders"](
                None,
                None,
                None,
                ctx=Context(
                    accounts={
                        "state": self.get_state_public_key(),
                        "user": self.get_user_account_public_key(sub_account_id),
                        "authority": self.wallet.public_key,
                    },
                    remaining_accounts=remaining_accounts,
                ),
            )
        ]
        for order_param in order_params:
            ix = self.program.instruction["place_spot_order"](
                order_param,
                ctx=Context(
                    accounts={
                        "state": self.get_state_public_key(),
                        "user": user_account_public_key,
                        "authority": self.wallet.public_key,
                    },
                    remaining_accounts=remaining_accounts,
                ),
            )
            ixs.append(ix)

        return ixs

    async def place_perp_order(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
        sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                self.get_increase_compute_ix(),
                (await self.get_place_perp_order_ix(order_params, sub_account_id))[-1],
            ]
        )

    async def get_place_perp_order_ix(
        self,
        order_params: OrderParams,
        sub_account_id: int = 0,
    ):
        user_account_public_key = self.get_user_account_public_key(sub_account_id)
        remaining_accounts = await self.get_remaining_accounts(
            readable_perp_market_indexes=[order_params.market_index],
            user_accounts=[await self.get_user_account(sub_account_id)],
        )

        ix = self.program.instruction["place_perp_order"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "authority": self.wallet.public_key,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return ix

    async def get_place_perp_orders_ix(
        self, order_params: List[OrderParams], sub_account_id: int = 0, cancel_all=True
    ):
        user_account_public_key = self.get_user_account_public_key(sub_account_id)
        readable_market_indexes = list(set([x.market_index for x in order_params]))
        remaining_accounts = await self.get_remaining_accounts(
            readable_perp_market_indexes=readable_market_indexes,
            user_accounts=[await self.get_user_account(sub_account_id)],
        )
        ixs = []
        if cancel_all:
            ixs.append(
                self.program.instruction["cancel_orders"](
                    None,
                    None,
                    None,
                    ctx=Context(
                        accounts={
                            "state": self.get_state_public_key(),
                            "user": self.get_user_account_public_key(sub_account_id),
                            "authority": self.wallet.public_key,
                        },
                        remaining_accounts=remaining_accounts,
                    ),
                )
            )
        for order_param in order_params:
            ix = self.program.instruction["place_perp_order"](
                order_param,
                ctx=Context(
                    accounts={
                        "state": self.get_state_public_key(),
                        "user": user_account_public_key,
                        "authority": self.wallet.public_key,
                    },
                    remaining_accounts=remaining_accounts,
                ),
            )
            ixs.append(ix)

        return ixs

    async def place_and_take(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
        sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                self.get_increase_compute_ix(),
                await self.get_place_and_take_ix(
                    order_params, maker_info, sub_account_id
                ),
            ]
        )

    async def get_place_and_take_ix(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
        sub_account_id: int = 0,
    ):
        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[order_params.market_index],
            user_accounts=[await self.get_user_account(sub_account_id)],
        )

        maker_order_id = None
        if maker_info is not None:
            maker_order_id = maker_info.order.order_id
            remaining_accounts.append(
                AccountMeta(pubkey=maker_info.maker, is_signer=False, is_writable=True)
            )

        return self.program.instruction["place_and_take_perp_order"](
            order_params,
            maker_order_id,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "user_stats": self.get_user_stats_public_key(),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def settle_lp(
        self,
        settlee_authority: Pubkey,
        market_index: int,
        sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                await self.get_settle_lp_ix(
                    settlee_authority, market_index, sub_account_id
                )
            ],
            signers=[],
        )

    async def get_settle_lp_ix(
        self, settlee_authority: Pubkey, market_index: int, sub_account_id: int = 0
    ):
        user_account_pubkey = get_user_account_public_key(
            self.program_id, settlee_authority, sub_account_id
        )
        user_account = await self.program.account["User"].fetch(user_account_pubkey)

        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index], user_accounts=[user_account]
        )

        return self.program.instruction["settle_lp"](
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": get_user_account_public_key(
                        self.program_id, settlee_authority, sub_account_id
                    ),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def get_user_spot_position(
        self,
        market_index: int,
        sub_account_id: int = 0,
    ) -> Optional[SpotPosition]:
        user = await get_user_account(self.program, self.authority, sub_account_id)

        found = False
        for position in user.spot_positions:
            if (
                position.market_index == market_index
                and not is_spot_position_available(position)
            ):
                found = True
                break

        if not found:
            return None

        return position

    async def get_user_position(
        self,
        market_index: int,
        sub_account_id: int = 0,
    ) -> Optional[PerpPosition]:
        user = await self.get_user(sub_account_id).get_user_account()

        found = False
        for position in user.perp_positions:
            if position.market_index == market_index and not is_available(position):
                found = True
                break

        if not found:
            return None

        return position

    async def close_position(
        self, market_index: int, limit_price: int = 0, sub_account_id: int = 0
    ):
        return await self.send_ixs(
            await self.get_close_position_ix(
                market_index, limit_price, sub_account_id=sub_account_id
            )
        )

    async def get_close_position_ix(
        self, market_index: int, limit_price: int = 0, sub_account_id: int = 0
    ):
        position = await self.get_user_position(market_index, sub_account_id)
        if position is None or position.base_asset_amount == 0:
            print("=> user has no position to close...")
            return

        order = self.default_order_params(
            order_type=OrderType.MARKET(),
            market_index=market_index,
            base_asset_amount=abs(int(position.base_asset_amount)),
            direction=PositionDirection.LONG()
            if position.base_asset_amount < 0
            else PositionDirection.SHORT(),
        )
        order.limit_price = limit_price
        order.reduce_only = True

        ix = await self.get_place_and_take_ix(order, sub_account_id=sub_account_id)
        return ix

    def default_order_params(
        self, order_type, market_index, base_asset_amount, direction
    ) -> OrderParams:
        return OrderParams(
            order_type,
            market_type=MarketType.PERP(),
            direction=direction,
            user_order_id=0,
            base_asset_amount=base_asset_amount,
            price=0,
            market_index=market_index,
            reduce_only=False,
            post_only=PostOnlyParams.NONE(),
            immediate_or_cancel=False,
            trigger_price=0,
            trigger_condition=OrderTriggerCondition.ABOVE(),
            oracle_price_offset=0,
            auction_duration=None,
            max_ts=None,
            auction_start_price=None,
            auction_end_price=None,
        )

    async def liquidate_spot(
        self,
        user_authority: Pubkey,
        asset_market_index: int,
        liability_market_index: int,
        max_liability_transfer: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                await self.get_liquidate_spot_ix(
                    user_authority,
                    asset_market_index,
                    liability_market_index,
                    max_liability_transfer,
                    user_sub_account_id,
                    liq_sub_account_id,
                )
            ]
        )

    async def get_liquidate_spot_ix(
        self,
        user_authority: Pubkey,
        asset_market_index: int,
        liability_market_index: int,
        max_liability_transfer: int,
        limit_price: int = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, sub_account_id=user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = await self.get_user_account(liq_sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            writable_spot_market_indexes=[liability_market_index, asset_market_index],
            user_accounts=[user_account, liq_user_account],
        )

        return self.program.instruction["liquidate_spot"](
            asset_market_index,
            liability_market_index,
            max_liability_transfer,
            limit_price,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": user_pk,
                    "user_stats": user_stats_pk,
                    "liquidator": liq_pk,
                    "liquidator_stats": liq_stats_pk,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def liquidate_perp(
        self,
        user_authority: Pubkey,
        market_index: int,
        max_base_asset_amount: int,
        limit_price: Optional[int] = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                await self.get_liquidate_perp_ix(
                    user_authority,
                    market_index,
                    max_base_asset_amount,
                    limit_price,
                    user_sub_account_id,
                    liq_sub_account_id,
                )
            ]
        )

    async def get_liquidate_perp_ix(
        self,
        user_authority: Pubkey,
        market_index: int,
        max_base_asset_amount: int,
        limit_price: Optional[int] = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = await self.get_user_account(liq_sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[user_account, liq_user_account],
        )

        return self.program.instruction["liquidate_perp"](
            market_index,
            max_base_asset_amount,
            limit_price,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": user_pk,
                    "user_stats": user_stats_pk,
                    "liquidator": liq_pk,
                    "liquidator_stats": liq_stats_pk,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def liquidate_perp_pnl_for_deposit(
        self,
        user_authority: Pubkey,
        perp_market_index: int,
        spot_market_index: int,
        max_pnl_transfer: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            self.get_liquidate_perp_pnl_for_deposit_ix(
                user_authority,
                perp_market_index,
                spot_market_index,
                max_pnl_transfer,
                user_sub_account_id,
                liq_sub_account_id,
            )
        )

    async def get_liquidate_perp_pnl_for_deposit_ix(
        self,
        user_authority: Pubkey,
        perp_market_index: int,
        spot_market_index: int,
        max_pnl_transfer: int,
        limit_price: int = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = await self.get_user_account(liq_sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[perp_market_index],
            writable_spot_market_indexes=[spot_market_index],
            user_accounts=[user_account, liq_user_account],
        )

        result = self.program.instruction["liquidate_perp_pnl_for_deposit"](
            perp_market_index,
            spot_market_index,
            max_pnl_transfer,
            limit_price,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": user_pk,
                    "user_stats": user_stats_pk,
                    "liquidator": liq_pk,
                    "liquidator_stats": liq_stats_pk,
                },
                remaining_accounts=remaining_accounts,
            ),
        )
        return result

    async def settle_pnl(
        self,
        user_authority: Pubkey,
        market_index: int,
        sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            await self.get_settle_pnl_ix(user_authority, market_index, sub_account_id)
        )

    async def get_settle_pnl_ix(
        self,
        user_authority: Pubkey,
        market_index: int,
        sub_account_id: int = 0,
    ):
        user_account_pubkey = get_user_account_public_key(
            self.program_id, user_authority, sub_account_id
        )
        user_account = await self.program.account["User"].fetch(user_account_pubkey)
        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            writable_spot_market_indexes=[QUOTE_SPOT_MARKET_INDEX],
            user_accounts=[user_account],
        )

        return [
            self.get_increase_compute_ix(),
            self.program.instruction["settle_pnl"](
                market_index,
                ctx=Context(
                    accounts={
                        "state": self.get_state_public_key(),
                        "authority": self.authority,
                        "user": get_user_account_public_key(
                            self.program_id, user_authority, sub_account_id
                        ),
                        "spot_market_vault": get_spot_market_vault_public_key(
                            self.program_id, QUOTE_SPOT_MARKET_INDEX
                        ),
                    },
                    remaining_accounts=remaining_accounts,
                ),
            ),
        ]

    async def resolve_spot_bankruptcy(
        self,
        user_authority: Pubkey,
        spot_market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                await self.get_resolve_spot_bankruptcy_ix(
                    user_authority,
                    spot_market_index,
                    user_sub_account_id,
                    liq_sub_account_id,
                )
            ]
        )

    async def get_resolve_spot_bankruptcy_ix(
        self,
        user_authority: Pubkey,
        spot_market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = await self.get_user_account(liq_sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index],
            user_accounts=[user_account, liq_user_account],
        )

        if_vault = get_insurance_fund_vault_public_key(
            self.program_id, spot_market_index
        )
        spot_vault = get_spot_market_vault_public_key(
            self.program_id, spot_market_index
        )
        dc_signer = get_drift_client_signer_public_key(self.program_id)

        return self.program.instruction["resolve_spot_bankruptcy"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": user_pk,
                    "user_stats": user_stats_pk,
                    "liquidator": liq_pk,
                    "liquidator_stats": liq_stats_pk,
                    "spot_market_vault": spot_vault,
                    "insurance_fund_vault": if_vault,
                    "drift_signer": dc_signer,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def resolve_perp_bankruptcy(
        self,
        user_authority: Pubkey,
        market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        return await self.send_ixs(
            [
                await self.get_resolve_perp_bankruptcy_ix(
                    user_authority,
                    market_index,
                    user_sub_account_id,
                    liq_sub_account_id,
                )
            ]
        )

    async def get_resolve_perp_bankruptcy_ix(
        self,
        user_authority: Pubkey,
        market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = 0,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = await self.get_user_account(liq_sub_account_id)

        remaining_accounts = await self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[user_account, liq_user_account],
        )

        if_vault = get_insurance_fund_vault_public_key(self.program_id, market_index)
        spot_vault = get_spot_market_vault_public_key(self.program_id, market_index)
        dc_signer = get_drift_client_signer_public_key(self.program_id)

        return self.program.instruction["resolve_perp_bankruptcy"](
            QUOTE_SPOT_MARKET_INDEX,
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": user_pk,
                    "user_stats": user_stats_pk,
                    "liquidator": liq_pk,
                    "liquidator_stats": liq_stats_pk,
                    "spot_market_vault": spot_vault,
                    "insurance_fund_vault": if_vault,
                    "drift_signer": dc_signer,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def settle_expired_market(
        self,
        market_index: int,
    ):
        return await self.send_ixs(
            [
                self.get_increase_compute_ix(),
                await self.get_settle_expired_market_ix(
                    market_index,
                ),
            ]
        )

    async def get_settle_expired_market_ix(
        self,
        market_index: int,
    ):
        market = await get_perp_market_account(self.program, market_index)

        market_account_infos = [
            AccountMeta(
                pubkey=market.pubkey,
                is_writable=True,
                is_signer=False,
            )
        ]

        oracle_account_infos = [
            AccountMeta(
                pubkey=market.amm.oracle,
                is_writable=False,
                is_signer=False,
            )
        ]

        spot_pk = get_spot_market_public_key(self.program_id, QUOTE_SPOT_MARKET_INDEX)
        spot_account_infos = [
            AccountMeta(
                pubkey=spot_pk,
                is_writable=True,
                is_signer=False,
            )
        ]

        remaining_accounts = (
            oracle_account_infos + spot_account_infos + market_account_infos
        )

        return self.program.instruction["settle_expired_market"](
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def request_remove_insurance_fund_stake(
        self, spot_market_index: int, amount: int
    ):
        return await self.send_ixs(
            await self.get_request_remove_insurance_fund_stake_ix(
                spot_market_index, amount
            )
        )

    async def get_request_remove_insurance_fund_stake_ix(
        self,
        spot_market_index: int,
        amount: int,
    ):
        ra = await self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index],
        )

        return self.program.instruction["request_remove_insurance_fund_stake"](
            spot_market_index,
            amount,
            ctx=Context(
                accounts={
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(
                        self.program_id, self.authority, spot_market_index
                    ),
                    "user_stats": get_user_stats_account_public_key(
                        self.program_id, self.authority
                    ),
                    "authority": self.authority,
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                },
                remaining_accounts=ra,
            ),
        )

    async def cancel_request_remove_insurance_fund_stake(self, spot_market_index: int):
        return await self.send_ixs(
            await self.get_cancel_request_remove_insurance_fund_stake_ix(
                spot_market_index
            )
        )

    async def get_cancel_request_remove_insurance_fund_stake_ix(
        self, spot_market_index: int
    ):
        ra = await self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index]
        )

        return self.program.instruction["cancel_request_remove_insurance_fund_stake"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(
                        self.program_id, self.authority, spot_market_index
                    ),
                    "user_stats": get_user_stats_account_public_key(
                        self.program_id, self.authority
                    ),
                    "authority": self.authority,
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "drift_signer": get_drift_client_signer_public_key(self.program_id),
                    "user_token_account": self.spot_market_atas[spot_market_index],
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=ra,
            ),
        )

    async def remove_insurance_fund_stake(self, spot_market_index: int):
        return await self.send_ixs(
            await self.get_remove_insurance_fund_stake_ix(spot_market_index)
        )

    async def get_remove_insurance_fund_stake_ix(self, spot_market_index: int):
        ra = await self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index],
        )

        return self.program.instruction["remove_insurance_fund_stake"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(
                        self.program_id, self.authority, spot_market_index
                    ),
                    "user_stats": get_user_stats_account_public_key(
                        self.program_id, self.authority
                    ),
                    "authority": self.authority,
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "drift_signer": get_drift_client_signer_public_key(self.program_id),
                    "user_token_account": self.spot_market_atas[spot_market_index],
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=ra,
            ),
        )

    async def add_insurance_fund_stake(self, spot_market_index: int, amount: int):
        return await self.send_ixs(
            await self.get_add_insurance_fund_stake_ix(spot_market_index, amount)
        )

    async def get_add_insurance_fund_stake_ix(
        self,
        spot_market_index: int,
        amount: int,
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index],
        )

        assert (
            self.spot_market_atas[spot_market_index] is not None
        ), "please set self.spot_market_atas[spot_market_index] as your spot ata pubkey before this ix"

        return self.program.instruction["add_insurance_fund_stake"](
            spot_market_index,
            amount,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(
                        self.program_id, self.authority, spot_market_index
                    ),
                    "user_stats": get_user_stats_account_public_key(
                        self.program_id, self.authority
                    ),
                    "authority": self.authority,
                    "spot_market_vault": get_spot_market_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "drift_signer": get_drift_client_signer_public_key(self.program_id),
                    "user_token_account": self.spot_market_atas[spot_market_index],
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def initialize_insurance_fund_stake(
        self,
        spot_market_index: int,
    ):
        return await self.send_ixs(
            self.get_initialize_insurance_fund_stake_ix(spot_market_index)
        )

    def get_initialize_insurance_fund_stake_ix(
        self,
        spot_market_index: int,
    ):
        return self.program.instruction["initialize_insurance_fund_stake"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(
                        self.program_id, self.authority, spot_market_index
                    ),
                    "user_stats": get_user_stats_account_public_key(
                        self.program_id, self.authority
                    ),
                    "state": get_state_public_key(self.program_id),
                    "authority": self.authority,
                    "payer": self.authority,
                    "rent": RENT,
                    "system_program": ID,
                }
            ),
        )

    async def update_amm(self, market_indexs: list[int]):
        return await self.send_ixs(await self.get_update_amm_ix(market_indexs))

    async def get_update_amm_ix(
        self,
        market_indexs: list[int],
    ):
        n = len(market_indexs)
        for _ in range(5 - n):
            market_indexs.append(100)

        market_infos = []
        oracle_infos = []
        for idx in market_indexs:
            if idx != 100:
                market = await get_perp_market_account(self.program, idx)
                market_infos.append(
                    AccountMeta(
                        pubkey=market.pubkey,
                        is_signer=False,
                        is_writable=True,
                    )
                )
                oracle_infos.append(
                    AccountMeta(
                        pubkey=market.amm.oracle, is_signer=False, is_writable=False
                    )
                )

        remaining_accounts = oracle_infos + market_infos

        return self.program.instruction["update_amms"](
            market_indexs,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def settle_revenue_to_insurance_fund(self, spot_market_index: int):
        return await self.program.rpc["settle_revenue_to_insurance_fund"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                    "spot_market_vault": get_spot_market_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "drift_signer": get_drift_client_signer_public_key(self.program_id),
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id,
                        spot_market_index,
                    ),
                    "token_program": TOKEN_PROGRAM_ID,
                }
            ),
        )
