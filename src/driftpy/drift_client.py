import json
from deprecated import deprecated
import requests
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import TransactionVersion, Legacy
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
from spl.token.instructions import get_associated_token_address
from anchorpy import Program, Context, Idl, Provider, Wallet
from pathlib import Path

import driftpy
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.address_lookup_table import get_address_lookup_table
from driftpy.constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.constants.numeric_constants import (
    QUOTE_SPOT_MARKET_INDEX,
)
from driftpy.drift_user import DriftUser
from driftpy.accounts import *

from driftpy.constants.config import DriftEnv, DRIFT_PROGRAM_ID, configs

from typing import Union, Optional, List
from driftpy.math.perp_position import is_available
from driftpy.math.spot_position import is_spot_position_available
from driftpy.math.spot_market import cast_to_spot_precision
from driftpy.name import encode_name
from driftpy.tx.standard_tx_sender import StandardTxSender
from driftpy.tx.types import TxSender, TxSigAndSlot
from spl.token.constants import ASSOCIATED_TOKEN_PROGRAM_ID
from solders.system_program import ID as SYS_PROGRAM_ID

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
        perp_market_indexes: list[int] = None,
        spot_market_indexes: list[int] = None,
        oracle_infos: list[OracleInfo] = None,
        tx_params: Optional[TxParams] = None,
        tx_version: Optional[TransactionVersion] = None,
        tx_sender: TxSender = None,
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

        self.active_sub_account_id = (
            active_sub_account_id if active_sub_account_id is not None else 0
        )
        self.sub_account_ids = (
            sub_account_ids
            if sub_account_ids is not None
            else [self.active_sub_account_id]
        )
        self.users = {}

        self.last_perp_market_seen_cache = {}
        self.last_spot_market_seen_cache = {}

        self.account_subscriber = account_subscription.get_drift_client_subscriber(
            self.program, perp_market_indexes, spot_market_indexes, oracle_infos
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

        self.tx_sender = (
            StandardTxSender(self.connection, opts) if tx_sender is None else tx_sender
        )

    async def subscribe(self):
        await self.account_subscriber.subscribe()
        for sub_account_id in self.sub_account_ids:
            await self.add_user(sub_account_id)

    async def add_user(self, sub_account_id: int):
        if sub_account_id in self.users:
            return

        user = DriftUser(
            drift_client=self,
            user_public_key=self.get_user_account_public_key(sub_account_id),
            sub_account_id=sub_account_id,
            account_subscription=self.account_subscription_config,
        )
        await user.subscribe()
        self.users[sub_account_id] = user

    def unsubscribe(self):
        self.account_subscriber.unsubscribe()

    def get_user(self, sub_account_id=None) -> DriftUser:
        sub_account_id = (
            sub_account_id if sub_account_id is not None else self.active_sub_account_id
        )
        if sub_account_id not in self.users:
            raise KeyError(f"No sub account id {sub_account_id} found")

        return self.users[sub_account_id]

    def get_user_account(self, sub_account_id=0) -> UserAccount:
        return self.get_user(sub_account_id).get_user_account()

    def switch_active_user(self, sub_account_id: int):
        self.active_sub_account_id = sub_account_id

    def get_state_public_key(self):
        return get_state_public_key(self.program_id)

    def get_user_account_public_key(self, sub_account_id=None) -> Pubkey:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)
        return get_user_account_public_key(
            self.program_id, self.authority, sub_account_id
        )

    def get_user_stats_public_key(self):
        return get_user_stats_account_public_key(self.program_id, self.authority)

    def get_associated_token_account_public_key(self, market_index: int) -> Pubkey:
        spot_market = self.get_spot_market_account(market_index)
        mint = spot_market.mint
        return get_associated_token_address(self.wallet.public_key, mint)

    def get_state_account(self) -> Optional[StateAccount]:
        state_and_slot = self.account_subscriber.get_state_account_and_slot()
        return getattr(state_and_slot, "data", None)

    def get_perp_market_account(self, market_index: int) -> Optional[PerpMarketAccount]:
        perp_market_and_slot = self.account_subscriber.get_perp_market_and_slot(
            market_index
        )
        return getattr(perp_market_and_slot, "data", None)

    def get_spot_market_account(self, market_index: int) -> Optional[SpotMarketAccount]:
        spot_market_and_slot = self.account_subscriber.get_spot_market_and_slot(
            market_index
        )
        return getattr(spot_market_and_slot, "data", None)

    def get_quote_spot_market_account(self) -> Optional[SpotMarketAccount]:
        spot_market_and_slot = self.account_subscriber.get_spot_market_and_slot(
            QUOTE_SPOT_MARKET_INDEX
        )
        return getattr(spot_market_and_slot, "data", None)

    def get_oracle_price_data(self, oracle: Pubkey) -> Optional[OraclePriceData]:
        oracle_price_data_and_slot = (
            self.account_subscriber.get_oracle_price_data_and_slot(oracle)
        )
        return getattr(oracle_price_data_and_slot, "data", None)

    def get_oracle_price_data_for_perp_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        oracle = self.get_perp_market_account(market_index).amm.oracle
        return self.get_oracle_price_data(oracle)

    def get_oracle_price_data_for_spot_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        oracle = self.get_spot_market_account(market_index).oracle
        return self.get_oracle_price_data(oracle)

    def convert_to_spot_precision(self, amount: Union[int, float], market_index) -> int:
        spot_market = self.get_spot_market_account(market_index)
        return cast_to_spot_precision(amount, spot_market)

    def convert_to_perp_precision(self, amount: Union[int, float]) -> int:
        return int(amount * BASE_PRECISION)

    def convert_to_price_precision(self, amount: Union[int, float]) -> int:
        return int(amount * PRICE_PRECISION)

    def get_sub_account_id_for_ix(self, sub_account_id: int = None):
        return (
            sub_account_id if sub_account_id is not None else self.active_sub_account_id
        )

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
    ) -> TxSigAndSlot:
        if isinstance(ixs, Instruction):
            ixs = [ixs]

        if self.tx_params.compute_units is not None:
            ixs.insert(0, set_compute_unit_limit(self.tx_params.compute_units))

        if self.tx_params.compute_units_price is not None:
            ixs.insert(1, set_compute_unit_price(self.tx_params.compute_units_price))

        if self.tx_version == Legacy:
            tx = await self.tx_sender.get_legacy_tx(ixs, self.wallet.payer, signers)
        elif self.tx_version == 0:
            if lookup_tables is None:
                lookup_tables = [await self.fetch_market_lookup_table()]
            tx = await self.tx_sender.get_versioned_tx(
                ixs, self.wallet.payer, lookup_tables, signers
            )
        else:
            raise NotImplementedError("unknown tx version", self.tx_version)

        return await self.tx_sender.send(tx)

    def get_remaining_accounts(
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
        ) = self.get_remaining_accounts_for_users(user_accounts)

        last_user_slot = self.get_user().get_user_account_and_slot().slot
        for perp_market_index, slot in self.last_perp_market_seen_cache.items():
            if slot > last_user_slot:
                self.add_perp_market_to_remaining_account_maps(
                    perp_market_index,
                    False,
                    oracle_map,
                    spot_market_map,
                    perp_market_map,
                )

        for spot_market_index, slot in self.last_spot_market_seen_cache.items():
            if slot > last_user_slot:
                self.add_spot_market_to_remaining_account_maps(
                    spot_market_index, False, oracle_map, spot_market_map
                )

        for perp_market_index in readable_perp_market_indexes:
            self.add_perp_market_to_remaining_account_maps(
                perp_market_index, False, oracle_map, spot_market_map, perp_market_map
            )

        for spot_market_index in readable_spot_market_indexes:
            self.add_spot_market_to_remaining_account_maps(
                spot_market_index, False, oracle_map, spot_market_map
            )

        for perp_market_index in writable_perp_market_indexes:
            self.add_perp_market_to_remaining_account_maps(
                perp_market_index, True, oracle_map, spot_market_map, perp_market_map
            )

        for spot_market_index in writable_spot_market_indexes:
            self.add_spot_market_to_remaining_account_maps(
                spot_market_index, True, oracle_map, spot_market_map
            )

        remaining_accounts = [
            *oracle_map.values(),
            *spot_market_map.values(),
            *perp_market_map.values(),
        ]

        return remaining_accounts

    def add_perp_market_to_remaining_account_maps(
        self,
        market_index: int,
        writable: bool,
        oracle_account_map: dict[str, AccountMeta],
        spot_market_account_map: dict[int, AccountMeta],
        perp_market_account_map: dict[int, AccountMeta],
    ) -> None:
        perp_market_account = self.get_perp_market_account(market_index)

        perp_market_account_map[market_index] = AccountMeta(
            pubkey=perp_market_account.pubkey, is_signer=False, is_writable=writable
        )

        oracle_account_map[str(perp_market_account.amm.oracle)] = AccountMeta(
            pubkey=perp_market_account.amm.oracle, is_signer=False, is_writable=False
        )

        self.add_spot_market_to_remaining_account_maps(
            perp_market_account.quote_spot_market_index,
            False,
            oracle_account_map,
            spot_market_account_map,
        )

    def add_spot_market_to_remaining_account_maps(
        self,
        market_index: int,
        writable: bool,
        oracle_account_map: dict[str, AccountMeta],
        spot_market_account_map: dict[int, AccountMeta],
    ) -> None:
        spot_market_account = self.get_spot_market_account(market_index)

        spot_market_account_map[market_index] = AccountMeta(
            pubkey=spot_market_account.pubkey, is_signer=False, is_writable=writable
        )

        if spot_market_account.oracle != Pubkey.default():
            oracle_account_map[str(spot_market_account.oracle)] = AccountMeta(
                pubkey=spot_market_account.oracle, is_signer=False, is_writable=False
            )

    def get_remaining_accounts_for_users(
        self, user_accounts: list[UserAccount]
    ) -> (dict[str, AccountMeta], dict[int, AccountMeta], dict[int, AccountMeta]):
        oracle_map = {}
        spot_market_map = {}
        perp_market_map = {}

        for user_account in user_accounts:
            for spot_position in user_account.spot_positions:
                if not is_spot_position_available(spot_position):
                    self.add_spot_market_to_remaining_account_maps(
                        spot_position.market_index, False, oracle_map, spot_market_map
                    )

                if spot_position.open_asks != 0 or spot_position.open_bids != 0:
                    self.add_spot_market_to_remaining_account_maps(
                        QUOTE_SPOT_MARKET_INDEX, False, oracle_map, spot_market_map
                    )

            for position in user_account.perp_positions:
                if not is_available(position):
                    self.add_perp_market_to_remaining_account_maps(
                        position.market_index,
                        False,
                        oracle_map,
                        spot_market_map,
                        perp_market_map,
                    )

        return oracle_map, spot_market_map, perp_market_map

    async def initialize_user(
        self,
        sub_account_id: int = 0,
        name: str = None,
        referrer_info: ReferrerInfo = None,
    ):
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

        ix = self.get_initialize_user_instructions(sub_account_id, name, referrer_info)
        ixs.append(ix)
        return (await self.send_ixs(ixs)).tx_sig

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
        self,
        sub_account_id: int = 0,
        name: str = DEFAULT_USER_NAME,
        referrer_info: ReferrerInfo = None,
    ) -> Instruction:
        user_public_key = self.get_user_account_public_key(sub_account_id)
        state_public_key = self.get_state_public_key()
        user_stats_public_key = self.get_user_stats_public_key()

        encoded_name = encode_name(name)

        remaining_accounts = []
        if referrer_info is not None:
            remaining_accounts.append(
                AccountMeta(referrer_info.referrer, is_writable=True, is_signer=False)
            )
            remaining_accounts.append(
                AccountMeta(
                    referrer_info.referrer_stats, is_writable=True, is_signer=False
                )
            )

        initialize_user_account_ix = self.program.instruction["initialize_user"](
            sub_account_id,
            encoded_name,
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
                remaining_accounts=remaining_accounts,
            ),
        )
        return initialize_user_account_ix

    async def deposit(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey = None,
        sub_account_id: int = None,
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
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_deposit_collateral_ix(
                    amount,
                    spot_market_index,
                    user_token_account,
                    sub_account_id,
                    reduce_only,
                    user_initialized,
                )
            ]
        )
        self.last_spot_market_seen_cache[spot_market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot

    def get_deposit_collateral_ix(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey = None,
        sub_account_id: int = None,
        reduce_only=False,
        user_initialized=True,
    ) -> Instruction:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        if user_initialized:
            remaining_accounts = self.get_remaining_accounts(
                writable_spot_market_indexes=[spot_market_index],
                user_accounts=[self.get_user_account(sub_account_id)],
            )
        else:
            raise Exception("not implemented...")

        user_token_account = (
            user_token_account
            if user_token_account is not None
            else self.get_associated_token_account_public_key(spot_market_index)
        )

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

    async def withdraw(
        self,
        amount: int,
        market_index: int,
        user_token_account: Pubkey,
        reduce_only: bool = False,
        sub_account_id: int = None,
    ):
        """withdraws from drift protocol (can also allow borrowing)

        Args:
            amount (int): amount to withdraw
            market_index (int):
            user_token_account (Pubkey): ata of the account to withdraw to
            reduce_only (bool, optional): if True will only withdraw existing funds else if False will allow taking out borrows. Defaults to False.
            sub_account_id (int, optional): subaccount. Defaults to 0.

        Returns:
            str: tx sig
        """
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_withdraw_collateral_ix(
                    amount,
                    market_index,
                    user_token_account,
                    reduce_only,
                    sub_account_id,
                )
            ]
        )
        self.last_spot_market_seen_cache[market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot

    def get_withdraw_collateral_ix(
        self,
        amount: int,
        market_index: int,
        user_token_account: Pubkey,
        reduce_only: bool = False,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        spot_market = self.get_spot_market_account(market_index)
        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)],
            writable_spot_market_indexes=[market_index],
        )
        dc_signer = get_drift_client_signer_public_key(self.program_id)

        return self.program.instruction["withdraw"](
            market_index,
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

    async def transfer_deposit(
        self,
        amount: int,
        market_index: int,
        from_sub_account_id: int,
        to_sub_account_id: int,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                await self.get_transfer_deposit_ix(
                    amount,
                    market_index,
                    from_sub_account_id,
                    to_sub_account_id,
                )
            ]
        )
        self.last_spot_market_seen_cache[market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    async def get_transfer_deposit_ix(
        self,
        amount: int,
        market_index: int,
        from_sub_account_id: int,
        to_sub_account_id: int,
    ):
        from_user_public_key = self.get_user_account_public_key(from_sub_account_id)
        to_user_public_key = self.get_user_account_public_key(to_sub_account_id)

        if from_sub_account_id not in self.users:
            from_user_account = await self.program.account["User"].fetch(
                from_user_public_key
            )
        else:
            from_user_account = self.get_user_account(from_sub_account_id)

        if to_sub_account_id not in self.users:
            to_user_account = await self.program.account["User"].fetch(
                to_user_public_key
            )
        else:
            to_user_account = self.get_user_account(to_sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            writable_spot_market_indexes=[
                market_index,
            ],
            user_accounts=[from_user_account, to_user_account],
        )

        ix = self.program.instruction["transfer_deposit"](
            market_index,
            amount,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user_stats": self.get_user_stats_public_key(),
                    "from_user": from_user_public_key,
                    "to_user": to_user_public_key,
                    "authority": self.wallet.public_key,
                    "spot_market_vault": self.get_spot_market_account(
                        market_index
                    ).vault,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return ix

    async def place_spot_order(
        self,
        order_params: OrderParams,
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_place_spot_order_ix(order_params, sub_account_id),
            ]
        )
        self.last_spot_market_seen_cache[
            order_params.market_index
        ] = tx_sig_and_slot.slot
        self.last_spot_market_seen_cache[QUOTE_SPOT_MARKET_INDEX] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    def get_place_spot_order_ix(
        self,
        order_params: OrderParams,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        order_params.set_spot()
        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            readable_spot_market_indexes=[
                QUOTE_SPOT_MARKET_INDEX,
                order_params.market_index,
            ],
            user_accounts=[self.get_user_account(sub_account_id)],
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

    async def place_perp_order(
        self,
        order_params: OrderParams,
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_place_perp_order_ix(order_params, sub_account_id),
            ]
        )
        self.last_perp_market_seen_cache[
            order_params.market_index
        ] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    def get_place_perp_order_ix(
        self,
        order_params: OrderParams,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        order_params.set_perp()
        user_account_public_key = self.get_user_account_public_key(sub_account_id)
        user_stats_public_key = self.get_user_stats_public_key()
        remaining_accounts = self.get_remaining_accounts(
            readable_perp_market_indexes=[order_params.market_index],
            user_accounts=[self.get_user_account(sub_account_id)],
        )

        ix = self.program.instruction["place_perp_order"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "userStats": user_stats_public_key,
                    "authority": self.wallet.public_key,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return ix

    async def place_orders(
        self,
        order_params: List[OrderParams],
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_place_orders_ix(order_params, sub_account_id),
            ]
        )

        for order_param in order_params:
            if is_variant(order_param.market_type, "Perp"):
                self.last_perp_market_seen_cache[
                    order_param.market_index
                ] = tx_sig_and_slot.slot
            else:
                self.last_spot_market_seen_cache[
                    order_param.market_index
                ] = tx_sig_and_slot.slot

        return tx_sig_and_slot.tx_sig

    def get_place_orders_ix(
        self,
        order_params: List[OrderParams],
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        user_account_public_key = self.get_user_account_public_key(sub_account_id)
        user_stats_public_key = self.get_user_stats_public_key()

        readable_perp_market_indexes = []
        readable_spot_market_indexes = []
        for order_param in order_params:
            order_param.check_market_type()

            if is_variant(order_param.market_type, "Perp"):
                readable_perp_market_indexes.append(order_param.market_index)
            else:
                if len(readable_spot_market_indexes) == 0:
                    readable_spot_market_indexes.append(QUOTE_SPOT_MARKET_INDEX)

                readable_spot_market_indexes.append(order_param.market_index)

        remaining_accounts = self.get_remaining_accounts(
            readable_perp_market_indexes=readable_perp_market_indexes,
            readable_spot_market_indexes=readable_spot_market_indexes,
            user_accounts=[self.get_user_account(sub_account_id)],
        )

        ix = self.program.instruction["place_orders"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "userStats": user_stats_public_key,
                    "authority": self.wallet.public_key,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return ix

    async def cancel_order(
        self,
        order_id: Optional[int] = None,
        sub_account_id: int = None,
    ):
        """cancel specific order (if order_id=None will be most recent order)

        Args:
            order_id (Optional[int], optional): Defaults to None.
            sub_account_id (int, optional): subaccount id which contains order. Defaults to 0.

        Returns:
            str: tx sig
        """
        return (
            await self.send_ixs(
                self.get_cancel_order_ix(order_id, sub_account_id),
            )
        ).tx_sig

    def get_cancel_order_ix(
        self, order_id: Optional[int] = None, sub_account_id: int = None
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)]
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

    async def cancel_order_by_user_id(
        self,
        user_order_id: int,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        return (
            await self.send_ixs(
                self.get_cancel_order_by_user_id_ix(user_order_id, sub_account_id),
            )
        ).tx_sig

    def get_cancel_order_by_user_id_ix(
        self, user_order_id: int, sub_account_id: int = None
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)]
        )

        return self.program.instruction["cancel_order_by_user_id"](
            user_order_id,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def cancel_orders(
        self,
        market_type: MarketType = None,
        market_index: int = None,
        direction: PositionDirection = None,
        sub_account_id: int = None,
    ):
        """cancel all existing orders on the book

        Args:
            market_type (MarketType, optional): only cancel orders for single market, used with market_index
            market_index (int, optional): only cancel orders for single market, used with market_type
            direction: (PositionDirection, optional): only cancel bids or asks
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            str: tx sig
        """
        return (
            await self.send_ixs(
                self.get_cancel_orders_ix(
                    market_type, market_index, direction, sub_account_id
                )
            )
        ).tx_sig

    def get_cancel_orders_ix(
        self,
        market_type: MarketType = None,
        market_index: int = None,
        direction: PositionDirection = None,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)]
        )

        return self.program.instruction["cancel_orders"](
            market_type,
            market_index,
            direction,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def cancel_and_place_orders(
        self,
        cancel_params: (
            Optional[MarketType],
            Optional[int],
            Optional[PositionDirection],
        ),
        place_order_params: List[OrderParams],
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            self.get_cancel_and_place_orders_ix(
                cancel_params, place_order_params, sub_account_id
            ),
        )

        for order_param in place_order_params:
            if is_variant(order_param.market_type, "Perp"):
                self.last_perp_market_seen_cache[
                    order_param.market_index
                ] = tx_sig_and_slot.slot
            else:
                self.last_spot_market_seen_cache[
                    order_param.market_index
                ] = tx_sig_and_slot.slot

        return tx_sig_and_slot.tx_sig

    def get_cancel_and_place_orders_ix(
        self,
        cancel_params: (
            Optional[MarketType],
            Optional[int],
            Optional[PositionDirection],
        ),
        place_order_params: List[OrderParams],
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        market_type, market_index, direction = cancel_params

        cancel_orders_ix = self.get_cancel_orders_ix(
            market_type, market_index, direction, sub_account_id
        )
        place_orders_ix = self.get_place_orders_ix(place_order_params, sub_account_id)
        return [cancel_orders_ix, place_orders_ix]

    async def modify_order(
        self,
        order_id: int,
        modify_order_params: ModifyOrderParams,
        sub_account_id: int = None,
    ):
        return (
            await self.send_ixs(
                [
                    self.get_modify_order_ix(
                        order_id, modify_order_params, sub_account_id
                    )
                ],
            )
        ).tx_sig

    def get_modify_order_ix(
        self,
        order_id: int,
        modify_order_params: ModifyOrderParams,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)],
        )

        return self.program.instruction["modify_order"](
            order_id,
            modify_order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def modify_order_by_user_id(
        self,
        user_order_id: int,
        modify_order_params: ModifyOrderParams,
        sub_account_id: int = None,
    ):
        return (
            await self.send_ixs(
                [
                    self.get_modify_order_by_user_id_ix(
                        user_order_id, modify_order_params, sub_account_id
                    )
                ],
            )
        ).tx_sig

    def get_modify_order_by_user_id_ix(
        self,
        user_order_id: int,
        modify_order_params: ModifyOrderParams,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)],
        )

        return self.program.instruction["modify_order_by_user_id"](
            user_order_id,
            modify_order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def place_and_take_perp_order(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_place_and_take_perp_order_ix(
                    order_params, maker_info, sub_account_id
                ),
            ]
        )
        self.last_perp_market_seen_cache[
            order_params.market_index
        ] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    def get_place_and_take_perp_order_ix(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        order_params.set_perp()

        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            writable_perp_market_indexes=[order_params.market_index],
            user_accounts=[self.get_user_account(sub_account_id)],
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

    async def add_liquidity(
        self, amount: int, market_index: int, sub_account_id: int = None
    ):
        """mint LP tokens and add liquidity to the DAMM

        Args:
            amount (int): amount of lp tokens to mint
            market_index (int): market you want to lp in
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            str: tx sig
        """
        tx_sig_and_slot = await self.send_ixs(
            [self.get_add_liquidity_ix(amount, market_index, sub_account_id)]
        )

        self.last_perp_market_seen_cache[market_index] = tx_sig_and_slot.slot

        return tx_sig_and_slot.tx_sig

    def get_add_liquidity_ix(
        self, amount: int, market_index: int, sub_account_id: int = None
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[self.get_user_account(sub_account_id)],
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
        self, amount: int, market_index: int, sub_account_id: int = None
    ):
        """burns LP tokens and removes liquidity to the DAMM

        Args:
            amount (int): amount of lp tokens to burn
            market_index (int):
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            str: tx sig
        """
        return (
            await self.send_ixs(
                [self.get_remove_liquidity_ix(amount, market_index, sub_account_id)]
            )
        ).tx_sig

    def get_remove_liquidity_ix(
        self, amount: int, market_index: int, sub_account_id: int = None
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[self.get_user_account(sub_account_id)],
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

    async def settle_lp(
        self,
        settlee_user_account_public_key: Pubkey,
        market_index: int,
    ):
        return (
            await self.send_ixs(
                [
                    await self.get_settle_lp_ix(
                        settlee_user_account_public_key, market_index
                    )
                ],
                signers=[],
            )
        ).tx_sig

    async def get_settle_lp_ix(
        self,
        settlee_user_account_public_key: Pubkey,
        market_index: int,
    ):
        settlee_user_account = await self.program.account["User"].fetch(
            settlee_user_account_public_key
        )

        remaining_accounts = self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            user_accounts=[settlee_user_account],
        )

        return self.program.instruction["settle_lp"](
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": settlee_user_account_public_key,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    def get_spot_position(
        self,
        market_index: int,
        sub_account_id: int = None,
    ) -> Optional[SpotPosition]:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        return self.get_user(sub_account_id).get_spot_position(market_index)

    def get_perp_position(
        self,
        market_index: int,
        sub_account_id: int = None,
    ) -> Optional[PerpPosition]:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)
        return self.get_user(sub_account_id).get_perp_position(market_index)

    async def liquidate_spot(
        self,
        user_authority: Pubkey,
        asset_market_index: int,
        liability_market_index: int,
        max_liability_transfer: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
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
        self.last_spot_market_seen_cache[asset_market_index] = tx_sig_and_slot.slot
        self.last_spot_market_seen_cache[liability_market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    async def get_liquidate_spot_ix(
        self,
        user_authority: Pubkey,
        asset_market_index: int,
        liability_market_index: int,
        max_liability_transfer: int,
        limit_price: int = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, sub_account_id=user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_sub_account_id = self.get_sub_account_id_for_ix(liq_sub_account_id)
        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = self.get_user_account(liq_sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
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
        liq_sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
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
        self.last_perp_market_seen_cache[market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    async def get_liquidate_perp_ix(
        self,
        user_authority: Pubkey,
        market_index: int,
        max_base_asset_amount: int,
        limit_price: Optional[int] = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_sub_account_id = self.get_sub_account_id_for_ix(liq_sub_account_id)
        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = self.get_user_account(liq_sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
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
        liq_sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            await self.get_liquidate_perp_pnl_for_deposit_ix(
                user_authority,
                perp_market_index,
                spot_market_index,
                max_pnl_transfer,
                user_sub_account_id,
                liq_sub_account_id,
            )
        )
        self.last_spot_market_seen_cache[spot_market_index] = tx_sig_and_slot.slot
        self.last_perp_market_seen_cache[perp_market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot.tx_sig

    async def get_liquidate_perp_pnl_for_deposit_ix(
        self,
        user_authority: Pubkey,
        perp_market_index: int,
        spot_market_index: int,
        max_pnl_transfer: int,
        limit_price: int = None,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_sub_account_id = self.get_sub_account_id_for_ix(liq_sub_account_id)
        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = self.get_user_account(liq_sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
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
        settlee_user_account_public_key: Pubkey,
        settlee_user_account: UserAccount,
        market_index: int,
    ):
        return (
            await self.send_ixs(
                self.get_settle_pnl_ix(
                    settlee_user_account_public_key, settlee_user_account, market_index
                )
            )
        ).tx_sig

    def get_settle_pnl_ix(
        self,
        settlee_user_public_key: Pubkey,
        settlee_user_account: UserAccount,
        market_index: int,
    ):
        remaining_accounts = self.get_remaining_accounts(
            writable_perp_market_indexes=[market_index],
            writable_spot_market_indexes=[QUOTE_SPOT_MARKET_INDEX],
            user_accounts=[settlee_user_account],
        )

        instruction = self.program.instruction["settle_pnl"](
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": settlee_user_public_key,
                    "spot_market_vault": get_spot_market_vault_public_key(
                        self.program_id, QUOTE_SPOT_MARKET_INDEX
                    ),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return instruction

    async def resolve_spot_bankruptcy(
        self,
        user_authority: Pubkey,
        spot_market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        return (
            await self.send_ixs(
                [
                    await self.get_resolve_spot_bankruptcy_ix(
                        user_authority,
                        spot_market_index,
                        user_sub_account_id,
                        liq_sub_account_id,
                    )
                ]
            )
        ).tx_sig

    async def get_resolve_spot_bankruptcy_ix(
        self,
        user_authority: Pubkey,
        spot_market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_sub_account_id = self.get_sub_account_id_for_ix(liq_sub_account_id)
        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = self.get_user_account(liq_sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
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
        liq_sub_account_id: int = None,
    ):
        return (
            await self.send_ixs(
                [
                    await self.get_resolve_perp_bankruptcy_ix(
                        user_authority,
                        market_index,
                        user_sub_account_id,
                        liq_sub_account_id,
                    )
                ]
            )
        ).tx_sig

    async def get_resolve_perp_bankruptcy_ix(
        self,
        user_authority: Pubkey,
        market_index: int,
        user_sub_account_id: int = 0,
        liq_sub_account_id: int = None,
    ):
        user_pk = get_user_account_public_key(
            self.program_id, user_authority, user_sub_account_id
        )
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_sub_account_id = self.get_sub_account_id_for_ix(liq_sub_account_id)
        liq_pk = self.get_user_account_public_key(liq_sub_account_id)
        liq_stats_pk = self.get_user_stats_public_key()

        user_account = await self.program.account["User"].fetch(user_pk)
        liq_user_account = self.get_user_account(liq_sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
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
        return (
            await self.send_ixs(
                [
                    await self.get_settle_expired_market_ix(
                        market_index,
                    ),
                ]
            )
        ).tx_sig

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
        return (
            await self.send_ixs(
                self.get_request_remove_insurance_fund_stake_ix(
                    spot_market_index, amount
                )
            )
        ).tx_sig

    def get_request_remove_insurance_fund_stake_ix(
        self,
        spot_market_index: int,
        amount: int,
    ):
        ra = self.get_remaining_accounts(
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
        return (
            await self.send_ixs(
                self.get_cancel_request_remove_insurance_fund_stake_ix(
                    spot_market_index
                )
            )
        ).tx_sig

    def get_cancel_request_remove_insurance_fund_stake_ix(
        self, spot_market_index: int, user_token_account: Pubkey = None
    ):
        ra = self.get_remaining_accounts(
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
                },
                remaining_accounts=ra,
            ),
        )

    async def remove_insurance_fund_stake(
        self, spot_market_index: int, user_token_account: Pubkey = None
    ):
        return (
            await self.send_ixs(
                self.get_remove_insurance_fund_stake_ix(
                    spot_market_index, user_token_account
                )
            )
        ).tx_sig

    def get_remove_insurance_fund_stake_ix(
        self, spot_market_index: int, user_token_account: Pubkey = None
    ):
        ra = self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index],
        )

        user_token_account = (
            user_token_account
            if user_token_account is not None
            else self.get_associated_token_account_public_key(spot_market_index)
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
                    "user_token_account": user_token_account,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=ra,
            ),
        )

    async def add_insurance_fund_stake(
        self, spot_market_index: int, amount: int, user_token_account: Pubkey = None
    ):
        return (
            await self.send_ixs(
                self.get_add_insurance_fund_stake_ix(
                    spot_market_index, amount, user_token_account
                )
            )
        ).tx_sig

    def get_add_insurance_fund_stake_ix(
        self, spot_market_index: int, amount: int, user_token_account: Pubkey = None
    ):
        remaining_accounts = self.get_remaining_accounts(
            writable_spot_market_indexes=[spot_market_index],
        )

        user_token_account = (
            user_token_account
            if user_token_account is not None
            else self.get_associated_token_account_public_key(spot_market_index)
        )

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
                    "user_token_account": user_token_account,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def initialize_insurance_fund_stake(
        self,
        spot_market_index: int,
    ):
        return (
            await self.send_ixs(
                self.get_initialize_insurance_fund_stake_ix(spot_market_index)
            )
        ).tx_sig

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

    @deprecated
    async def open_position(
        self,
        direction: PositionDirection,
        amount: int,
        market_index: int,
        sub_account_id: int = None,
        limit_price: int = 0,
        ioc: bool = False,
    ):
        return (
            await self.send_ixs(
                self.get_open_position_ix(
                    direction,
                    amount,
                    market_index,
                    sub_account_id,
                    limit_price,
                    ioc,
                ),
            )
        ).tx_sig

    @deprecated
    def get_open_position_ix(
        self,
        direction: PositionDirection,
        amount: int,
        market_index: int,
        sub_account_id: int = None,
        limit_price: int = 0,
        ioc: bool = False,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        order_params = OrderParams(
            order_type=OrderType.Market(),
            direction=direction,
            market_index=market_index,
            base_asset_amount=amount,
            price=limit_price,
        )

        ix = self.get_place_and_take_perp_order_ix(
            order_params, sub_account_id=sub_account_id
        )
        return ix

    @deprecated
    async def close_position(
        self, market_index: int, limit_price: int = 0, sub_account_id: int = None
    ):
        return (
            await self.send_ixs(
                self.get_close_position_ix(
                    market_index, limit_price, sub_account_id=sub_account_id
                )
            )
        ).tx_sig

    @deprecated
    def get_close_position_ix(
        self, market_index: int, limit_price: int = 0, sub_account_id: int = None
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        position = self.get_perp_position(market_index, sub_account_id)
        if position is None or position.base_asset_amount == 0:
            print("=> user has no position to close...")
            return

        order_params = OrderParams(
            order_type=OrderType.Market(),
            market_index=market_index,
            base_asset_amount=abs(int(position.base_asset_amount)),
            direction=PositionDirection.Long()
            if position.base_asset_amount < 0
            else PositionDirection.Short(),
            price=limit_price,
            reduce_only=True,
        )

        ix = self.get_place_and_take_perp_order_ix(
            order_params, sub_account_id=sub_account_id
        )
        return ix

    async def update_amm(self, market_indexs: list[int]):
        return (await self.send_ixs(self.get_update_amm_ix(market_indexs))).tx_sig

    def get_update_amm_ix(
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
                market = self.get_perp_market_account(idx)
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

    def create_associated_token_account_idempotent_instruction(
        self, account: Pubkey, payer: Pubkey, owner: Pubkey, mint: Pubkey
    ):
        return Instruction(
            accounts=[
                AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
                AccountMeta(pubkey=account, is_signer=False, is_writable=True),
                AccountMeta(pubkey=owner, is_signer=False, is_writable=False),
                AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
                AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
                AccountMeta(
                    pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False
                ),
                AccountMeta(pubkey=RENT, is_signer=False, is_writable=False),
            ],
            program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
            data=bytes([0x01]),
        )

    async def get_swap_flash_loan_ix(
        self,
        out_market_index: int,
        in_market_index: int,
        amount_in: int,
        in_ata: Pubkey,
        out_ata: Pubkey,
        limit_price: Optional[int] = 0,
        reduce_only: Optional[SwapReduceOnly] = False,
        user_account_public_key: Optional[Pubkey] = None,
    ):
        user_public_key_to_use = (
            user_account_public_key
            if user_account_public_key
            else (self.get_user_account_public_key())
        )

        user_accounts = []

        try:
            user_accounts.append(self.get_user().get_user_account_and_slot().data)
        except:
            pass  # ignore

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=user_accounts,
            writable_spot_market_indexes=[out_market_index, in_market_index],
            readable_spot_market_indexes=[QUOTE_SPOT_MARKET_INDEX],
        )

        out_market = self.get_spot_market_account(out_market_index)
        in_market = self.get_spot_market_account(in_market_index)

        sysvar_pubkey = Pubkey.from_string(
            "Sysvar1nstructions1111111111111111111111111"
        )

        begin_swap_ix = self.program.instruction["begin_swap"](
            in_market_index,
            out_market_index,
            amount_in,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_public_key_to_use,
                    "user_stats": self.get_user_stats_public_key(),
                    "authority": self.wallet.public_key,
                    "out_spot_market_vault": out_market.vault,
                    "in_spot_market_vault": in_market.vault,
                    "in_token_account": in_ata,
                    "out_token_account": out_ata,
                    "token_program": TOKEN_PROGRAM_ID,
                    "drift_signer": self.get_state_account().signer,
                    "instructions": sysvar_pubkey,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        end_swap_ix = self.program.instruction["end_swap"](
            in_market_index,
            out_market_index,
            limit_price,
            reduce_only,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_public_key_to_use,
                    "user_stats": self.get_user_stats_public_key(),
                    "authority": self.wallet.public_key,
                    "out_spot_market_vault": out_market.vault,
                    "in_spot_market_vault": in_market.vault,
                    "in_token_account": in_ata,
                    "out_token_account": out_ata,
                    "token_program": TOKEN_PROGRAM_ID,
                    "drift_signer": self.get_state_account().signer,
                    "instructions": sysvar_pubkey,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return begin_swap_ix, end_swap_ix

    async def get_jupiter_swap_ix_v6(
        self,
        out_market_idx: int,
        in_market_idx: int,
        amount: int,
        out_ata: Optional[Pubkey] = None,
        in_ata: Optional[Pubkey] = None,
        slippage_bps: Optional[int] = None,
        quote=None,
        reduce_only: Optional[SwapReduceOnly] = None,
        user_account_public_key: Optional[Pubkey] = None,
    ):
        pre_instructions = []
        JUPITER_URL = "https://quote-api.jup.ag/v6"

        out_market = self.get_spot_market_account(out_market_idx)
        in_market = self.get_spot_market_account(in_market_idx)

        if slippage_bps is None:
            slippage_bps = 10

        if quote is None:
            url = f"{JUPITER_URL}/quote?inputMint={str(in_market.mint)}&outputMint={str(out_market.mint)}&amount={amount}&slippageBps={slippage_bps}"

            quote_resp = requests.get(url)

            if quote_resp.status_code != 200:
                raise Exception("Couldn't get a Jupiter quote")

            quote = quote_resp.json()

        if out_ata is None:
            out_ata: Pubkey = self.get_associated_token_account_public_key(
                out_market.market_index
            )

            ai = await self.connection.get_account_info(out_ata)

            if not ai:
                pre_instructions.append(
                    self.create_associated_token_account_idempotent_instruction(
                        out_ata,
                        self.wallet.public_key,
                        self.wallet.public_key,
                        out_market.mint,
                    )
                )

        if in_ata is None:
            in_ata: Pubkey = self.get_associated_token_account_public_key(
                in_market.market_index
            )

            ai = await self.connection.get_account_info(in_ata)

            if not ai:
                pre_instructions.append(
                    self.create_associated_token_account_idempotent_instruction(
                        in_ata,
                        self.wallet.public_key,
                        self.wallet.public_key,
                        in_market.mint,
                    )
                )

        data = {
            "quoteResponse": quote,
            "userPublicKey": str(self.wallet.public_key),
            "destinationTokenAccount": str(out_ata),
        }

        swap_ix_resp = requests.post(
            f"{JUPITER_URL}/swap-instructions",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            data=json.dumps(data),
        )

        if swap_ix_resp.status_code != 200:
            raise Exception("Couldn't get Jupiter swap ix")

        swap_ix_json = swap_ix_resp.json()

        compute_budget_ix = swap_ix_json.get("computeBudgetInstructions")
        swap_ix = swap_ix_json.get("swapInstruction")
        address_table_lookups = swap_ix_json.get("addressLookupTableAddresses")

        swap_ixs = [compute_budget_ix, swap_ix]

        begin_swap_ix, end_swap_ix = await self.get_swap_flash_loan_ix(
            out_market_idx,
            in_market_idx,
            amount,
            in_ata,
            out_ata,
            None,
            reduce_only,
            user_account_public_key,
        )

        ixs = [*pre_instructions, begin_swap_ix, *swap_ixs, end_swap_ix]

        return ixs, address_table_lookups
