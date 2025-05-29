import asyncio
import base64
import os
import random
import string
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import List, Optional, Tuple, Union, cast

import anchorpy
import requests
from anchorpy.program.context import Context
from anchorpy.program.core import Program
from anchorpy.provider import Provider, Wallet
from anchorpy_core.idl import Idl
from deprecated import deprecated
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Processed
from solana.rpc.types import TxOpts
from solders import system_program
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import ID
from solders.system_program import ID as SYS_PROGRAM_ID
from solders.sysvar import RENT
from solders.transaction import Legacy, TransactionVersion
from spl.token.constants import ASSOCIATED_TOKEN_PROGRAM_ID, TOKEN_PROGRAM_ID
from spl.token.instructions import (
    CloseAccountParams,
    InitializeAccountParams,
    close_account,
    get_associated_token_address,
    initialize_account,
)

import driftpy
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts import (
    DataAndSlot,
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    UserAccount,
)
from driftpy.accounts.cache.drift_client import CachedDriftClientAccountSubscriber
from driftpy.accounts.demo.drift_client import DemoDriftClientAccountSubscriber
from driftpy.accounts.get_accounts import get_perp_market_account
from driftpy.address_lookup_table import get_address_lookup_table
from driftpy.addresses import (
    get_drift_client_signer_public_key,
    get_high_leverage_mode_config_public_key,
    get_insurance_fund_stake_public_key,
    get_insurance_fund_vault_public_key,
    get_protected_maker_mode_config_public_key,
    get_sequencer_public_key_and_bump,
    get_serum_signer_public_key,
    get_signed_msg_user_account_public_key,
    get_spot_market_public_key,
    get_spot_market_vault_public_key,
    get_state_public_key,
    get_user_account_public_key,
    get_user_stats_account_public_key,
)
from driftpy.constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.constants.config import (
    DEVNET_SEQUENCER_PROGRAM_ID,
    DRIFT_PROGRAM_ID,
    SEQUENCER_PROGRAM_ID,
    DriftEnv,
    configs,
)
from driftpy.constants.numeric_constants import QUOTE_SPOT_MARKET_INDEX
from driftpy.constants.spot_markets import WRAPPED_SOL_MINT
from driftpy.decode.utils import decode_name
from driftpy.drift_user import DriftUser
from driftpy.drift_user_stats import DriftUserStats, UserStatsSubscriptionConfig
from driftpy.math.perp_position import is_available
from driftpy.math.spot_market import cast_to_spot_precision
from driftpy.math.spot_position import is_spot_position_available
from driftpy.name import encode_name
from driftpy.swift.create_verify_ix import create_minimal_ed25519_verify_ix
from driftpy.tx.standard_tx_sender import StandardTxSender
from driftpy.tx.types import TxSender, TxSigAndSlot
from driftpy.types import (
    MakerInfo,
    MarketType,
    ModifyOrderParams,
    OracleInfo,
    Order,
    OrderParams,
    OrderParamsBitFlag,
    OrderType,
    PerpPosition,
    PhoenixV1FulfillmentConfigAccount,
    PositionDirection,
    ReferrerInfo,
    SequenceAccount,
    SerumV3FulfillmentConfigAccount,
    SignedMsgOrderParams,
    SignedMsgOrderParamsDelegateMessage,
    SignedMsgOrderParamsMessage,
    SpotPosition,
    SwapReduceOnly,
    TxParams,
    is_variant,
)

DEFAULT_USER_NAME = "Main Account"

DEFAULT_TX_OPTIONS = TxOpts(skip_confirmation=False, preflight_commitment=Processed)


@dataclass
class JitoParams:
    jito_keypair: Keypair
    block_engine_url: str
    blockhash_refresh_rate: Optional[int] = None
    leader_refresh_rate: Optional[int] = None
    tip_amount: Optional[int] = None


class DriftClient:
    """This class is the main way to interact with Drift Protocol including
    depositing, opening new positions, closing positions, placing orders, etc.
    """

    def __init__(
        self,
        connection: AsyncClient,
        wallet: Keypair | Wallet,
        env: DriftEnv | None = "mainnet",
        opts: TxOpts = DEFAULT_TX_OPTIONS,
        authority: Pubkey | None = None,
        account_subscription: AccountSubscriptionConfig = AccountSubscriptionConfig.default(),
        perp_market_indexes: list[int] | None = None,
        spot_market_indexes: list[int] | None = None,
        oracle_infos: list[OracleInfo] | None = None,
        tx_params: Optional[TxParams] = None,
        tx_version: Optional[TransactionVersion] = None,
        tx_sender: TxSender | None = None,
        active_sub_account_id: Optional[int] = None,
        sub_account_ids: Optional[list[int]] = None,
        market_lookup_table: Optional[Pubkey] = None,
        market_lookup_tables: Optional[list[Pubkey]] = None,
        jito_params: Optional[JitoParams] = None,
        tx_sender_blockhash_commitment: Commitment | None = None,
        enforce_tx_sequencing: bool = False,
    ):
        """Initializes the drift client object

        Args:
            connection (AsyncClient): Solana RPC connection
            wallet (Keypair | Wallet): Wallet for transaction signing
            env (DriftEnv | None, optional): Drift environment. Defaults to "mainnet".
            opts (TxOpts, optional): Transaction options. Defaults to DEFAULT_TX_OPTIONS.
            authority (Pubkey | None, optional): Authority for transactions. If None, defaults to wallet's public key.
            account_subscription (AccountSubscriptionConfig, optional): Config for account subscriptions. Defaults to AccountSubscriptionConfig.default().
            perp_market_indexes (list[int] | None, optional): List of perp market indexes to subscribe to. Defaults to None.
            spot_market_indexes (list[int] | None, optional): List of spot market indexes to subscribe to. Defaults to None.
            oracle_infos (list[OracleInfo] | None, optional): List of oracle infos to subscribe to. Defaults to None.
            tx_params (Optional[TxParams], optional): Transaction parameters. Defaults to None.
            tx_version (Optional[TransactionVersion], optional): Transaction version. Defaults to None.
            tx_sender (TxSender | None, optional): Custom transaction sender. Defaults to None.
            active_sub_account_id (Optional[int], optional): Active sub-account ID. Defaults to None.
            sub_account_ids (Optional[list[int]], optional): List of sub-account IDs. Defaults to None.
            market_lookup_table (Optional[Pubkey], optional): Market lookup table pubkey (deprecated). Defaults to None.
            market_lookup_tables (Optional[list[Pubkey]], optional): List of market lookup table pubkeys. Defaults to None.
            jito_params (Optional[JitoParams], optional): Parameters for Jito MEV integration. Defaults to None.
            tx_sender_blockhash_commitment (Commitment | None, optional): Blockhash commitment for tx sender. Defaults to None.
            enforce_tx_sequencing (bool, optional): Whether to enforce transaction sequencing. Defaults to False.
        """
        self.connection = connection
        self.signer_public_key: Optional[Pubkey] = None

        file = Path(str(next(iter(driftpy.__path__))) + "/idl/drift.json")
        idl = Idl.from_json(file.read_text())

        if isinstance(wallet, Keypair):
            wallet = Wallet(wallet)

        provider = Provider(connection, wallet, opts)
        self.program_id = DRIFT_PROGRAM_ID
        self.program = Program(idl, self.program_id, provider)

        if authority is None:
            authority = wallet.public_key

        self.wallet: Wallet = wallet
        self.authority = authority

        self.active_sub_account_id = (
            active_sub_account_id if active_sub_account_id is not None else 0
        )
        self.sub_account_ids = (
            sub_account_ids
            if sub_account_ids is not None
            else [self.active_sub_account_id]
        )
        self.users: dict[int, DriftUser] = {}
        self.user_stats: dict[Pubkey, DriftUserStats] = {}

        self.last_perp_market_seen_cache = {}
        self.last_spot_market_seen_cache = {}

        self.account_subscriber = account_subscription.get_drift_client_subscriber(
            self.program, perp_market_indexes, spot_market_indexes, oracle_infos
        )
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")

        self.account_subscription_config = account_subscription

        # deprecated, use market_lookup_tables instead
        self.market_lookup_table = None
        if env is not None:
            self.market_lookup_table = (
                market_lookup_table
                if market_lookup_table is not None
                else configs[env].market_lookup_table
            )
        # deprecated, use market_lookup_table_accounts instead
        self.market_lookup_table_account: Optional[AddressLookupTableAccount] = None

        self.market_lookup_tables = None
        if env is not None and market_lookup_tables is not None:
            self.market_lookup_tables = market_lookup_tables
        else:
            self.market_lookup_tables = configs[env].market_lookup_tables

        self.market_lookup_table_accounts: list[AddressLookupTableAccount] = []

        if tx_params is None:
            tx_params = TxParams(600_000, 0)

        self.tx_params = tx_params

        self.tx_version = tx_version if tx_version is not None else 0

        self.enforce_tx_sequencing = enforce_tx_sequencing
        if self.enforce_tx_sequencing is True:
            file = Path(
                str(next(iter(driftpy.__path__))) + "/idl/sequence_enforcer.json"
            )
            idl = Idl.from_json(file.read_text())

            provider = Provider(connection, wallet, opts)
            self.sequence_enforcer_pid = (
                SEQUENCER_PROGRAM_ID
                if env == "mainnet"
                else DEVNET_SEQUENCER_PROGRAM_ID
            )
            self.sequence_enforcer_program = Program(
                idl,
                self.sequence_enforcer_pid,
                provider,
            )
            self.sequence_number_by_subaccount = {}
            self.sequence_bump_by_subaccount = {}
            self.sequence_initialized_by_subaccount = {}
            self.sequence_address_by_subaccount = {}
            self.resetting_sequence = False

        if jito_params is not None:
            from driftpy.tx.jito_tx_sender import JitoTxSender

            self.tx_sender = JitoTxSender(
                self,
                opts,
                jito_params.block_engine_url,
                jito_params.jito_keypair,
                blockhash_refresh_interval_secs=jito_params.blockhash_refresh_rate,
                tip_amount=jito_params.tip_amount,
            )
        else:
            self.tx_sender = (
                StandardTxSender(
                    self.connection,
                    opts,
                    blockhash_commitment=(
                        tx_sender_blockhash_commitment
                        if tx_sender_blockhash_commitment is not None
                        else Commitment("finalized")
                    ),
                )
                if tx_sender is None
                else tx_sender
            )

    async def subscribe(self):
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")
        await self.account_subscriber.subscribe()
        if self.enforce_tx_sequencing:
            await self.load_sequence_info()
        for sub_account_id in self.sub_account_ids:
            await self.add_user(sub_account_id)
        await self.add_user_stats(self.authority)

    async def fetch_market_lookup_table_accounts(self):
        if self.market_lookup_tables is None:
            raise ValueError("No market lookup tables found")
        self.market_lookup_table_accounts: list[
            AddressLookupTableAccount
        ] = await asyncio.gather(
            *[
                get_address_lookup_table(self.connection, table)
                for table in self.market_lookup_tables
            ]
        )
        return self.market_lookup_table_accounts

    def resurrect(self, spot_markets, perp_markets, spot_oracles, perp_oracles):
        if not isinstance(self.account_subscriber, CachedDriftClientAccountSubscriber):
            raise ValueError(
                'You can only resurrect a DriftClient that was initialized with AccountSubscriptionConfig("cached")'
            )
        self.account_subscriber.resurrect(
            spot_markets, perp_markets, spot_oracles, perp_oracles
        )

    async def add_user(self, sub_account_id: int):
        if sub_account_id in self.users:
            return

        user = DriftUser(
            drift_client=self,
            user_public_key=self.get_user_account_public_key(sub_account_id),
            account_subscription=self.account_subscription_config,
        )
        await user.subscribe()
        self.users[sub_account_id] = user

    async def add_user_stats(self, authority: Pubkey):
        if authority in self.user_stats:
            return

        self.user_stats[authority] = DriftUserStats(
            self,
            self.get_user_stats_public_key(),
            UserStatsSubscriptionConfig("confirmed"),
        )

        # don't subscribe because up to date UserStats is not required
        await self.user_stats[authority].fetch_accounts()

    async def unsubscribe(self):
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")
        await self.account_subscriber.unsubscribe()

    def get_user(self, sub_account_id: int | None = None) -> DriftUser:
        sub_account_id = (
            sub_account_id if sub_account_id is not None else self.active_sub_account_id
        )
        if sub_account_id not in self.sub_account_ids:
            raise KeyError(
                f"No sub account id {sub_account_id} found, need to include in `sub_account_ids` when initializing DriftClient"
            )

        if sub_account_id not in self.users:
            raise KeyError(
                f"No sub account id {sub_account_id} found, need to call `await DriftClient.subscribe()` first"
            )

        return self.users[sub_account_id]

    def get_user_account(self, sub_account_id=None) -> UserAccount:
        return self.get_user(sub_account_id).get_user_account()

    def get_user_stats(self, authority=None) -> DriftUserStats:
        if authority is None:
            authority = self.authority

        if authority not in self.user_stats:
            raise KeyError(
                f"No UserStats for {authority} found, need to call `await DriftClient.subscribe()` first"
            )

        return self.user_stats[authority]

    def switch_active_user(self, sub_account_id: int):
        self.active_sub_account_id = sub_account_id

    def get_state_public_key(self):
        return get_state_public_key(self.program_id)

    def get_signer_public_key(self) -> Pubkey:
        if self.signer_public_key:
            return self.signer_public_key

        self.signer_public_key = get_drift_client_signer_public_key(self.program_id)
        return self.signer_public_key

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
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")
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

    def get_oracle_price_data(self, oracle_id: str) -> Optional[OraclePriceData]:
        if self.account_subscriber is None:
            return None

        data_and_slot = self.account_subscriber.get_oracle_price_data_and_slot(
            oracle_id
        )

        if data_and_slot is None:
            return None

        return getattr(data_and_slot, "data", None)

    def get_oracle_price_data_for_perp_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")

        if isinstance(self.account_subscriber, DemoDriftClientAccountSubscriber):
            raise ValueError("Cannot get market for demo subscriber")

        data = self.account_subscriber.get_oracle_price_data_and_slot_for_perp_market(
            market_index
        )
        if isinstance(data, DataAndSlot):
            return getattr(
                data,
                "data",
                None,
            )

        return data

    def get_oracle_price_data_for_spot_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        if self.account_subscriber is None:
            return None
        if isinstance(self.account_subscriber, DemoDriftClientAccountSubscriber):
            raise ValueError("Cannot get market for demo subscriber")

        data = self.account_subscriber.get_oracle_price_data_and_slot_for_spot_market(
            market_index
        )
        if isinstance(data, DataAndSlot):
            return getattr(
                data,
                "data",
                None,
            )

        return data

    def convert_to_spot_precision(self, amount: Union[int, float], market_index) -> int:
        spot_market = self.get_spot_market_account(market_index)
        return cast_to_spot_precision(amount, spot_market)

    def convert_to_perp_precision(self, amount: Union[int, float]) -> int:
        return int(amount * BASE_PRECISION)

    def convert_to_price_precision(self, amount: Union[int, float]) -> int:
        return int(amount * PRICE_PRECISION)

    def get_sub_account_id_for_ix(self, sub_account_id: Optional[int] = None):
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
        tx_version: Optional[Union[Legacy, int]] = None,
        sequencer_subaccount: Optional[int] = None,
    ) -> TxSigAndSlot:
        if isinstance(ixs, Instruction):
            ixs = [ixs]

        if not tx_version:
            tx_version = self.tx_version

        compute_unit_instructions = []
        if self.tx_params.compute_units is not None:
            compute_unit_instructions.append(
                set_compute_unit_limit(self.tx_params.compute_units)
            )

        if self.tx_params.compute_units_price is not None:
            compute_unit_instructions.append(
                set_compute_unit_price(self.tx_params.compute_units_price)
            )

        ixs[0:0] = compute_unit_instructions

        subaccount = sequencer_subaccount or self.active_sub_account_id

        if (
            self.enforce_tx_sequencing
            and self.sequence_initialized_by_subaccount[subaccount]
            and not self.resetting_sequence
        ):
            sequence_instruction = self.get_check_and_set_sequence_number_ix(
                self.sequence_number_by_subaccount[subaccount], subaccount
            )
            ixs.insert(len(compute_unit_instructions), sequence_instruction)

        if tx_version == Legacy:
            tx = await self.tx_sender.get_legacy_tx(ixs, self.wallet.payer, signers)
        elif tx_version == 0:
            if lookup_tables is None:
                lookup_tables = await self.fetch_market_lookup_table_accounts()
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
        if not perp_market_account:
            raise ValueError(
                f"No perp market account found for market index {market_index}"
            )

        perp_market_account_map[market_index] = AccountMeta(
            pubkey=perp_market_account.pubkey, is_signer=False, is_writable=writable
        )

        oracle_writable = writable and is_variant(
            perp_market_account.amm.oracle_source, "Prelaunch"
        )
        oracle_account_map[str(perp_market_account.amm.oracle)] = AccountMeta(
            pubkey=perp_market_account.amm.oracle,
            is_signer=False,
            is_writable=oracle_writable,
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

    def add_spot_fulfillment_accounts(
        self,
        market_index: int,
        remaining_accounts: list[AccountMeta],
        fulfillment_config: Optional[
            Union[SerumV3FulfillmentConfigAccount, PhoenixV1FulfillmentConfigAccount]
        ] = None,
    ) -> None:
        if fulfillment_config is not None:
            if isinstance(fulfillment_config, SerumV3FulfillmentConfigAccount):
                self.add_serum_remaining_accounts(
                    market_index, remaining_accounts, fulfillment_config
                )
            elif isinstance(fulfillment_config, PhoenixV1FulfillmentConfigAccount):
                self.add_phoenix_remaining_accounts(
                    market_index, remaining_accounts, fulfillment_config
                )
            else:
                raise Exception(
                    f"unknown fulfillment config: {type(fulfillment_config)}"
                )
        else:
            remaining_accounts.append(
                AccountMeta(
                    self.get_spot_market_account(market_index).vault,
                    is_writable=False,
                    is_signer=False,
                )
            )
            remaining_accounts.append(
                AccountMeta(
                    self.get_spot_market_account(QUOTE_SPOT_MARKET_INDEX).vault,
                    is_writable=False,
                    is_signer=False,
                )
            )

    def add_serum_remaining_accounts(
        self,
        market_index: int,
        remaining_accounts: list[AccountMeta],
        fulfillment_config: SerumV3FulfillmentConfigAccount,
    ) -> None:
        remaining_accounts.append(
            AccountMeta(fulfillment_config.pubkey, is_writable=False, is_signer=False)
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_program_id, is_writable=False, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_market, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_request_queue,
                is_writable=True,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_event_queue, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_bids, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_asks, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_base_vault, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_quote_vault, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.serum_open_orders, is_writable=True, is_signer=False
            )
        )
        serum_signer_key = get_serum_signer_public_key(
            fulfillment_config.serum_program_id,
            fulfillment_config.serum_market,
            fulfillment_config.serum_signer_nonce,
        )
        remaining_accounts.append(
            AccountMeta(serum_signer_key, is_writable=False, is_signer=False)
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_signer_public_key(), is_writable=False, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(TOKEN_PROGRAM_ID, is_writable=False, is_signer=False)
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_spot_market_account(market_index).vault,
                is_writable=True,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_spot_market_account(QUOTE_SPOT_MARKET_INDEX).vault,
                is_writable=True,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_state_account().srm_vault, is_writable=False, is_signer=False
            )
        )

    def add_phoenix_remaining_accounts(
        self,
        market_index: int,
        remaining_accounts: list[AccountMeta],
        fulfillment_config: PhoenixV1FulfillmentConfigAccount,
    ) -> None:
        remaining_accounts.append(
            AccountMeta(fulfillment_config.pubkey, is_writable=False, is_signer=False)
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.phoenix_program_id,
                is_writable=False,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.phoenix_log_authority,
                is_writable=False,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.phoenix_market, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_signer_public_key(), is_writable=False, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.phoenix_base_vault, is_writable=True, is_signer=False
            )
        )
        remaining_accounts.append(
            AccountMeta(
                fulfillment_config.phoenix_quote_vault,
                is_writable=True,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_spot_market_account(market_index).vault,
                is_writable=True,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(
                self.get_spot_market_account(QUOTE_SPOT_MARKET_INDEX).vault,
                is_writable=True,
                is_signer=False,
            )
        )
        remaining_accounts.append(
            AccountMeta(TOKEN_PROGRAM_ID, is_writable=False, is_signer=False)
        )

    async def initialize_user(
        self,
        sub_account_id: int = 0,
        name: str = None,
        referrer_info: ReferrerInfo = None,
    ) -> Signature:
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
                    "authority": self.wallet.payer.pubkey(),
                    "payer": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
                    "payer": self.wallet.payer.pubkey(),
                    "rent": RENT,
                    "system_program": ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )
        return initialize_user_account_ix

    def random_string(self, length: int) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    async def get_wrapped_sol_account_creation_ixs(
        self, amount: int, include_rent: bool = True
    ) -> (List[Instruction], Pubkey):
        wallet_pubkey = self.wallet.public_key
        seed = self.random_string(32)
        wrapped_sol_account = Pubkey.create_with_seed(
            wallet_pubkey, seed, TOKEN_PROGRAM_ID
        )
        result = {"ixs": [], "pubkey": wrapped_sol_account}

        LAMPORTS_PER_SOL: int = 1_000_000_000
        rent_space_lamports = int(LAMPORTS_PER_SOL / 100)
        lamports = amount + rent_space_lamports if include_rent else rent_space_lamports

        create_params = system_program.CreateAccountWithSeedParams(
            from_pubkey=wallet_pubkey,
            to_pubkey=wrapped_sol_account,
            base=wallet_pubkey,
            seed=seed,
            lamports=lamports,
            space=165,
            owner=TOKEN_PROGRAM_ID,
        )

        result["ixs"].append(system_program.create_account_with_seed(create_params))

        initialize_params = InitializeAccountParams(
            program_id=TOKEN_PROGRAM_ID,
            account=wrapped_sol_account,
            mint=WRAPPED_SOL_MINT,
            owner=wallet_pubkey,
        )

        result["ixs"].append(initialize_account(initialize_params))

        return result["ixs"], result["pubkey"]

    async def deposit(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey,
        sub_account_id: Optional[int] = None,
        reduce_only=False,
        user_initialized=True,
    ) -> TxSigAndSlot:
        """deposits collateral into protocol

        Args:
            amount (int): amount to deposit
            spot_market_index (int):
            user_token_account (Pubkey):
            sub_account_id (int, optional): subaccount to deposit into. Defaults to 0.
            reduce_only (bool, optional): paying back borrow vs depositing new assets. Defaults to False.
            user_initialized (bool, optional): if need to initialize user account too set this to False. Defaults to True.

        Returns:
            TxSigAndSlot: tx sig and slot
        """
        tx_sig_and_slot = await self.send_ixs(
            await self.get_deposit_collateral_ix(
                amount,
                spot_market_index,
                user_token_account,
                sub_account_id,
                reduce_only,
                user_initialized,
            )
        )
        self.last_spot_market_seen_cache[spot_market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot

    async def get_deposit_collateral_ix(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: Pubkey,
        sub_account_id: Optional[int] = None,
        reduce_only: Optional[bool] = False,
        user_initialized: Optional[bool] = True,
    ) -> List[Instruction]:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)
        spot_market_account = self.get_spot_market_account(spot_market_index)
        if not spot_market_account:
            raise Exception("Spot market account not found")

        is_sol_market = spot_market_account.mint == WRAPPED_SOL_MINT
        signer_authority = self.wallet.public_key

        create_WSOL_token_account = (
            is_sol_market and user_token_account == signer_authority
        )

        if user_initialized:
            remaining_accounts = self.get_remaining_accounts(
                writable_spot_market_indexes=[spot_market_index],
                user_accounts=[self.get_user_account(sub_account_id)],
            )
        else:
            raise Exception("not implemented...")

        instructions = []

        if create_WSOL_token_account:
            ixs, ata_pubkey = await self.get_wrapped_sol_account_creation_ixs(amount)
            instructions.extend(ixs)
            user_token_account = ata_pubkey

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
        deposit_ix = self.program.instruction["deposit"](
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
                    "authority": self.wallet.payer.pubkey(),
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )
        instructions.append(deposit_ix)
        if create_WSOL_token_account:
            close_account_params = CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=user_token_account,
                dest=signer_authority,
                owner=signer_authority,
            )
            close_account_ix = close_account(close_account_params)
            instructions.append(close_account_ix)
        return instructions

    async def withdraw(
        self,
        amount: int,
        market_index: int,
        user_token_account: Pubkey,
        reduce_only: bool = False,
        sub_account_id: int = None,
    ) -> TxSigAndSlot:
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
            await self.get_withdraw_collateral_ix(
                amount,
                market_index,
                user_token_account,
                reduce_only,
                sub_account_id,
            )
        )
        self.last_spot_market_seen_cache[market_index] = tx_sig_and_slot.slot
        return tx_sig_and_slot

    async def get_withdraw_collateral_ix(
        self,
        amount: int,
        market_index: int,
        user_token_account: Pubkey,
        reduce_only: bool = False,
        sub_account_id: Optional[int] = None,
    ) -> List[Instruction]:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        spot_market = self.get_spot_market_account(market_index)
        if not spot_market:
            raise Exception("Spot market account not found")

        is_sol_market = spot_market.mint == WRAPPED_SOL_MINT
        signer_authority = self.wallet.public_key

        create_WSOL_token_account = (
            is_sol_market and user_token_account == signer_authority
        )

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)],
            writable_spot_market_indexes=[market_index],
        )
        dc_signer = self.get_signer_public_key()

        instructions = []
        temp_wsol_account_pubkey = None

        if create_WSOL_token_account:
            # Withdraw SOL to main wallet - create temporary WSOL account
            # Pass include_rent=False as rent is not needed for withdrawal destination
            (
                ixs,
                temp_wsol_account_pubkey,
            ) = await self.get_wrapped_sol_account_creation_ixs(amount, False)
            instructions.extend(ixs)
            user_token_account_for_ix = temp_wsol_account_pubkey
        else:
            account_info = await self.connection.get_account_info(user_token_account)
            if not account_info.value:
                create_ata_ix = (
                    self.create_associated_token_account_idempotent_instruction(
                        account=user_token_account,
                        payer=signer_authority,
                        owner=signer_authority,
                        mint=spot_market.mint,
                    )
                )
                instructions.append(create_ata_ix)
            user_token_account_for_ix = user_token_account

        withdraw_ix = self.program.instruction[
            "withdraw"
        ](
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
                    "user_token_account": user_token_account_for_ix,  # Use correct account
                    "authority": signer_authority,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts,
            ),
        )
        instructions.append(withdraw_ix)

        if create_WSOL_token_account and temp_wsol_account_pubkey:
            close_account_params = CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=temp_wsol_account_pubkey,
                dest=signer_authority,
                owner=signer_authority,
            )
            close_account_ix = close_account(close_account_params)
            instructions.append(close_account_ix)

        return instructions

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
        self.last_spot_market_seen_cache[order_params.market_index] = (
            tx_sig_and_slot.slot
        )
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
        self.last_perp_market_seen_cache[order_params.market_index] = (
            tx_sig_and_slot.slot
        )
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

        if OrderParamsBitFlag.is_update_high_leverage_mode(order_params.bit_flags):
            remaining_accounts.append(
                AccountMeta(
                    pubkey=get_high_leverage_mode_config_public_key(self.program_id),
                    is_writable=True,
                    is_signer=False,
                )
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
                self.last_perp_market_seen_cache[order_param.market_index] = (
                    tx_sig_and_slot.slot
                )
            else:
                self.last_spot_market_seen_cache[order_param.market_index] = (
                    tx_sig_and_slot.slot
                )

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
    ) -> Signature:
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
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
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
    ) -> Signature:
        """cancel all existing orders on the book

        Args:
            market_type (MarketType, optional): only cancel orders for single market, used with market_index
            market_index (int, optional): only cancel orders for single market, used with market_type
            direction: (PositionDirection, optional): only cancel bids or asks
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            Signature: tx sig
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
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def cancel_and_place_orders(
        self,
        cancel_params: Tuple[
            Optional[MarketType],
            Optional[int],
            Optional[PositionDirection],
        ],
        place_order_params: List[OrderParams],
        sub_account_id: Optional[int] = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            self.get_cancel_and_place_orders_ix(
                cancel_params, place_order_params, sub_account_id
            ),
        )

        for order_param in place_order_params:
            if is_variant(order_param.market_type, "Perp"):
                self.last_perp_market_seen_cache[order_param.market_index] = (
                    tx_sig_and_slot.slot
                )
            else:
                self.last_spot_market_seen_cache[order_param.market_index] = (
                    tx_sig_and_slot.slot
                )

        return tx_sig_and_slot.tx_sig

    def get_cancel_and_place_orders_ix(
        self,
        cancel_params: Tuple[
            Optional[MarketType],
            Optional[int],
            Optional[PositionDirection],
        ],
        place_order_params: List[OrderParams],
        sub_account_id: Optional[int] = None,
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
        sub_account_id: Optional[int] = None,
    ) -> Signature:
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
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def modify_order_by_user_id(
        self,
        user_order_id: int,
        modify_order_params: ModifyOrderParams,
        sub_account_id: int = None,
    ) -> Signature:
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
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def place_and_take_perp_order(
        self,
        order_params: OrderParams,
        maker_info: Union[MakerInfo, List[MakerInfo]] = None,
        referrer_info: ReferrerInfo = None,
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_place_and_take_perp_order_ix(
                    order_params, maker_info, referrer_info, sub_account_id
                ),
            ]
        )
        self.last_perp_market_seen_cache[order_params.market_index] = (
            tx_sig_and_slot.slot
        )
        return tx_sig_and_slot.tx_sig

    def get_place_and_take_perp_order_ix(
        self,
        order_params: OrderParams,
        maker_info: Union[MakerInfo, List[MakerInfo]] = None,
        referrer_info: ReferrerInfo = None,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        order_params.set_perp()

        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        maker_infos = (
            maker_info
            if isinstance(maker_info, list)
            else [maker_info]
            if maker_info
            else []
        )

        user_accounts = [self.get_user_account(sub_account_id)]
        for maker_info in maker_infos:
            user_accounts.append(maker_info.maker_user_account)

        remaining_accounts = self.get_remaining_accounts(
            writable_perp_market_indexes=[order_params.market_index],
            user_accounts=user_accounts,
        )

        if OrderParamsBitFlag.is_update_high_leverage_mode(order_params.bit_flags):
            remaining_accounts.append(
                AccountMeta(
                    pubkey=get_high_leverage_mode_config_public_key(self.program_id),
                    is_writable=True,
                    is_signer=False,
                )
            )

        for maker_info in maker_infos:
            remaining_accounts.append(
                AccountMeta(pubkey=maker_info.maker, is_signer=False, is_writable=True)
            )
            remaining_accounts.append(
                AccountMeta(
                    pubkey=maker_info.maker_stats, is_signer=False, is_writable=True
                )
            )

        if referrer_info is not None:
            referrer_is_maker = referrer_info.referrer in [
                maker_info.maker for maker_info in maker_infos
            ]
            if not referrer_is_maker:
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=referrer_info.referrer, is_signer=False, is_writable=True
                    )
                )
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=referrer_info.referrer_stats,
                        is_signer=False,
                        is_writable=True,
                    )
                )

        return self.program.instruction["place_and_take_perp_order"](
            order_params,
            None,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "user_stats": self.get_user_stats_public_key(),
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def place_and_take_spot_order(
        self,
        order_params: OrderParams,
        fulfillment_config: Optional[
            Union[SerumV3FulfillmentConfigAccount, PhoenixV1FulfillmentConfigAccount]
        ] = None,
        maker_info: Union[MakerInfo, List[MakerInfo]] = None,
        referrer_info: ReferrerInfo = None,
        sub_account_id: int = None,
    ):
        tx_sig_and_slot = await self.send_ixs(
            [
                self.get_place_and_take_spot_order_ix(
                    order_params,
                    fulfillment_config,
                    maker_info,
                    referrer_info,
                    sub_account_id,
                ),
            ]
        )
        self.last_spot_market_seen_cache[order_params.market_index] = (
            tx_sig_and_slot.slot
        )
        return tx_sig_and_slot.tx_sig

    def get_place_and_take_spot_order_ix(
        self,
        order_params: OrderParams,
        fulfillment_config: Optional[
            Union[SerumV3FulfillmentConfigAccount, PhoenixV1FulfillmentConfigAccount]
        ] = None,
        maker_info: Union[MakerInfo, List[MakerInfo]] = None,
        referrer_info: ReferrerInfo = None,
        sub_account_id: int = None,
    ):
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        order_params.set_spot()

        user_account_public_key = self.get_user_account_public_key(sub_account_id)

        user_accounts = [self.get_user_account(sub_account_id)]
        maker_infos = (
            maker_info
            if isinstance(maker_info, list)
            else [maker_info]
            if maker_info
            else []
        )
        for maker_info in maker_infos:
            user_accounts.append(maker_info.maker_user_account)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=user_accounts,
            writable_spot_market_indexes=[
                order_params.market_index,
                QUOTE_SPOT_MARKET_INDEX,
            ],
        )

        for maker_info in maker_infos:
            remaining_accounts.append(
                AccountMeta(pubkey=maker_info.maker, is_signer=False, is_writable=True)
            )
            remaining_accounts.append(
                AccountMeta(
                    pubkey=maker_info.maker_stats, is_signer=False, is_writable=True
                )
            )

        if referrer_info is not None:
            referrer_is_maker = (
                referrer_info.referrer == maker_info.maker if maker_info else False
            )
            if not referrer_is_maker:
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=referrer_info.referrer, is_signer=False, is_writable=True
                    )
                )
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=referrer_info.referrer_stats,
                        is_signer=False,
                        is_writable=True,
                    )
                )

        self.add_spot_fulfillment_accounts(
            order_params.market_index, remaining_accounts, fulfillment_config
        )

        return self.program.instruction["place_and_take_spot_order"](
            order_params,
            fulfillment_config,
            None,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "user_stats": self.get_user_stats_public_key(),
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def add_liquidity(
        self, amount: int, market_index: int, sub_account_id: int = None
    ) -> Signature:
        """mint LP tokens and add liquidity to the DAMM

        Args:
            amount (int): amount of lp tokens to mint
            market_index (int): market you want to lp in
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            Signature: tx sig
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
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def remove_liquidity(
        self, amount: int, market_index: int, sub_account_id: int = None
    ) -> Signature:
        """burns LP tokens and removes liquidity to the DAMM

        Args:
            amount (int): amount of lp tokens to burn
            market_index (int):
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            Signature: tx sig
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
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def settle_lp(
        self,
        settlee_user_account_public_key: Pubkey,
        market_index: int,
    ) -> Signature:
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

    def decode_signed_msg_order_params_message(
        self, signed_msg_order_params_buf: bytes, is_delegate: bool = False
    ) -> Union[SignedMsgOrderParamsMessage, SignedMsgOrderParamsDelegateMessage]:
        payload = signed_msg_order_params_buf[8:]
        if is_delegate:
            return self.program.coder.types.decode(
                "SignedMsgOrderParamsDelegateMessage", payload
            )
        else:
            return self.program.coder.types.decode(
                "SignedMsgOrderParamsMessage", payload
            )

    def sign_message(self, message: bytes) -> bytes:
        """Sign a message with the wallet keypair.

        Args:
            message: The message to sign

        Returns:
            The signature
        """

        return self.wallet.payer.sign_message(message).to_bytes()

    def encode_signed_msg_order_params_message(
        self,
        order_params_message: Union[
            dict, SignedMsgOrderParamsMessage, SignedMsgOrderParamsDelegateMessage
        ],
        delegate_signer: bool = False,
    ) -> bytes:
        """Borsh encode signedMsg order params message

        Args:
            order_params_message: The order params message to encode
            delegate_signer: Whether to use delegate message format

        Returns:
            The encoded buffer
        """

        anchor_ix_name = (
            "global:SignedMsgOrderParamsMessage"
            if not delegate_signer
            else "global:SignedMsgOrderParamsDelegateMessage"
        )
        prefix = bytes.fromhex(sha256(anchor_ix_name.encode()).hexdigest()[:16])

        # Convert Pubkey to bytes if it's a delegate message
        if delegate_signer and isinstance(
            order_params_message, SignedMsgOrderParamsDelegateMessage
        ):
            taker_pubkey_bytes = bytes(order_params_message.taker_pubkey)
            order_params_message = SignedMsgOrderParamsDelegateMessage(
                signed_msg_order_params=order_params_message.signed_msg_order_params,
                slot=order_params_message.slot,
                uuid=order_params_message.uuid,
                taker_pubkey=list(taker_pubkey_bytes),
                take_profit_order_params=order_params_message.take_profit_order_params,
                stop_loss_order_params=order_params_message.stop_loss_order_params,
            )

        encoded = self.program.coder.types.encode(
            "SignedMsgOrderParamsDelegateMessage"
            if delegate_signer
            else "SignedMsgOrderParamsMessage",
            order_params_message,
        )

        buf = prefix + encoded
        return buf

    def sign_signed_msg_order_params_message(
        self,
        order_params_message: Union[
            dict, SignedMsgOrderParamsMessage, SignedMsgOrderParamsDelegateMessage
        ],
        delegate_signer: bool = False,
    ) -> SignedMsgOrderParams:
        """Sign a SignedMsgOrderParamsMessage

        Args:
            order_params_message: The order params message to sign
            delegate_signer: Whether to use delegate message format

        Returns:
            The signed order params
        """
        borsh_buf = self.encode_signed_msg_order_params_message(
            order_params_message, delegate_signer
        )
        order_params = borsh_buf.hex().encode()

        return SignedMsgOrderParams(
            order_params=order_params, signature=self.sign_message(order_params)
        )

    async def place_signed_msg_taker_order(
        self,
        signed_msg_order_params: SignedMsgOrderParams,
        market_index: int,
        taker_info: dict,
        preceding_ixs: list[Instruction] = [],
        override_ix_count: Optional[int] = None,
        include_high_leverage_mode_config: Optional[bool] = False,
    ) -> TxSigAndSlot:
        ixs = await self.get_place_signed_msg_taker_perp_order_ixs(
            signed_msg_order_params,
            market_index,
            taker_info,
            None,
            preceding_ixs,
            override_ix_count,
            include_high_leverage_mode_config,
        )
        return await self.send_ixs(ixs)

    async def get_place_signed_msg_taker_perp_order_ixs(
        self,
        signed_msg_order_params: Union[dict, SignedMsgOrderParams],
        market_index: int,
        taker_info: dict,
        authority: Optional[Pubkey] = None,
        preceding_ixs: list[Instruction] = [],
        override_ix_count: Optional[int] = None,
        include_high_leverage_mode_config: Optional[bool] = False,
    ):
        if not authority and not taker_info["taker_user_account"]:
            raise Exception("authority or taker_user_account must be provided")

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[taker_info["taker_user_account"]],
            readable_perp_market_indexes=[market_index],
        )

        if include_high_leverage_mode_config:
            remaining_accounts.append(
                AccountMeta(
                    pubkey=get_high_leverage_mode_config_public_key(self.program_id),
                    is_writable=True,
                    is_signer=False,
                )
            )
        authority_to_use = authority or taker_info["taker_user_account"].authority

        print(f"Signed msg order params: {signed_msg_order_params}")
        if isinstance(signed_msg_order_params, SignedMsgOrderParams):
            signed_msg_order_params = {
                "signature": signed_msg_order_params.signature,
                "order_params": signed_msg_order_params.order_params,
            }

        message_length_buffer = int.to_bytes(
            len(signed_msg_order_params["order_params"]), 2, "little"
        )

        signed_msg_ix_data = b"".join(
            [
                signed_msg_order_params["signature"],
                bytes(authority_to_use),
                message_length_buffer,
                signed_msg_order_params["order_params"],
            ]
        )

        signed_msg_order_params_signature_ix = create_minimal_ed25519_verify_ix(
            override_ix_count or len(preceding_ixs) + 1,
            12,
            signed_msg_ix_data,
            0,
        )

        is_delegate_signer = False
        if (
            taker_info.get("signing_authority")
            and taker_info.get("taker_user_account")
            and taker_info["taker_user_account"].delegate
            and taker_info["signing_authority"]
            == taker_info["taker_user_account"].delegate
        ):
            is_delegate_signer = True

        sysvar_pubkey = Pubkey.from_string(
            "Sysvar1nstructions1111111111111111111111111"
        )

        place_taker_signed_msg_perp_order_ix = self.program.instruction[
            "place_signed_msg_taker_order"
        ](
            signed_msg_ix_data,
            is_delegate_signer,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": taker_info["taker"],
                    "user_stats": taker_info["taker_stats"],
                    "signed_msg_user_orders": get_signed_msg_user_account_public_key(
                        self.program_id,
                        taker_info["taker_user_account"].authority,
                    ),
                    "authority": self.wallet.payer.pubkey(),
                    "ix_sysvar": sysvar_pubkey,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return [
            signed_msg_order_params_signature_ix,
            place_taker_signed_msg_perp_order_ix,
        ]

    async def place_and_make_signed_msg_perp_order(
        self,
        signed_msg_order_params: SignedMsgOrderParams,
        signed_msg_order_uuid: bytes,
        taker_info: dict,
        order_params: OrderParams,
    ):
        ixs = await self.get_place_and_make_signed_msg_perp_order_ixs(
            signed_msg_order_params,
            signed_msg_order_uuid,
            taker_info,
            order_params,
        )
        lookup_tables = await self.fetch_market_lookup_table_accounts()
        result = await self.send_ixs(ixs, lookup_tables=lookup_tables)
        self.last_perp_market_seen_cache[order_params.market_index] = result.slot
        return result.tx_sig

    async def get_place_and_make_signed_msg_perp_order_ixs(
        self,
        signed_msg_order_params: SignedMsgOrderParams,
        signed_msg_order_uuid: bytes,
        taker_info: dict,
        order_params: OrderParams,
        referrer_info: Optional[ReferrerInfo] = None,
        sub_account_id: Optional[int] = None,
        preceding_ixs: list[Instruction] = [],
        override_ix_count: Optional[int] = None,
        include_high_leverage_mode_config: Optional[bool] = False,
    ) -> list[Instruction]:
        (
            signed_msg_order_signature_ix,
            place_taker_signed_msg_perp_order_ix,
        ) = await self.get_place_signed_msg_taker_perp_order_ixs(
            signed_msg_order_params,
            order_params.market_index,
            taker_info,
            None,
            preceding_ixs,
            override_ix_count,
        )

        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)
        user_stats_public_key = self.get_user_stats_public_key()
        user = self.get_user_account_public_key(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[
                self.get_user_account(sub_account_id),
                taker_info["taker_user_account"],
            ],
            writable_perp_market_indexes=[order_params.market_index],
        )

        if include_high_leverage_mode_config:
            remaining_accounts.append(
                AccountMeta(
                    pubkey=get_high_leverage_mode_config_public_key(self.program_id),
                    is_writable=True,
                    is_signer=False,
                )
            )

        if referrer_info:
            remaining_accounts.append(
                AccountMeta(
                    pubkey=referrer_info.referrer, is_writable=True, is_signer=False
                )
            )
            remaining_accounts.append(
                AccountMeta(
                    pubkey=referrer_info.referrer_stats,
                    is_writable=True,
                    is_signer=False,
                )
            )

        place_and_make_ix = self.program.instruction[
            "place_and_make_signed_msg_perp_order"
        ](
            order_params,
            signed_msg_order_uuid,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user,
                    "user_stats": user_stats_public_key,
                    "taker": taker_info["taker"],
                    "taker_stats": taker_info["taker_stats"],
                    "authority": self.wallet.payer.pubkey(),
                    "taker_signed_msg_user_orders": get_signed_msg_user_account_public_key(
                        self.program_id, taker_info["taker_user_account"].authority
                    ),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return [
            signed_msg_order_signature_ix,
            place_taker_signed_msg_perp_order_ix,
            place_and_make_ix,
        ]

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
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
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
        lookup_tables = await self.fetch_market_lookup_table_accounts()
        return (
            await self.send_ixs(
                self.get_settle_pnl_ix(
                    settlee_user_account_public_key, settlee_user_account, market_index
                ),
                lookup_tables=lookup_tables,
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
                    "authority": self.wallet.payer.pubkey(),
                    "user": settlee_user_public_key,
                    "spot_market_vault": get_spot_market_vault_public_key(
                        self.program_id, QUOTE_SPOT_MARKET_INDEX
                    ),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return instruction

    def get_settle_pnl_ixs(
        self, users: dict[Pubkey, UserAccount], market_indexes: list[int]
    ) -> list[Instruction]:
        ixs: list[Instruction] = []
        for pubkey, account in users.items():
            for market_index in market_indexes:
                ix = self.get_settle_pnl_ix(pubkey, account, market_index)
                ixs.append(ix)

        return ixs

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
        dc_signer = self.get_signer_public_key(self.program_id)

        return self.program.instruction["resolve_spot_bankruptcy"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.wallet.payer.pubkey(),
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
        dc_signer = self.get_signer_public_key(self.program_id)

        return self.program.instruction["resolve_perp_bankruptcy"](
            QUOTE_SPOT_MARKET_INDEX,
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
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
                    "authority": self.wallet.payer.pubkey(),
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "drift_signer": self.get_signer_public_key(self.program_id),
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
                    "authority": self.wallet.payer.pubkey(),
                    "spot_market_vault": get_spot_market_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(
                        self.program_id, spot_market_index
                    ),
                    "drift_signer": self.get_signer_public_key(self.program_id),
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
                    "authority": self.wallet.payer.pubkey(),
                    "payer": self.wallet.payer.pubkey(),
                    "rent": RENT,
                    "system_program": ID,
                }
            ),
        )

    async def fill_perp_order(
        self,
        user_account_pubkey: Pubkey,
        user_account: UserAccount,
        order: Order,
        maker_info: Optional[Union[MakerInfo, list[MakerInfo]]],
        referrer_info: Optional[ReferrerInfo],
    ):
        return (
            await self.send_ixs(
                [
                    await self.get_fill_perp_order_ix(
                        user_account_pubkey,
                        user_account,
                        order,
                        maker_info,
                        referrer_info,
                    )
                ]
            )
        ).tx_sig

    async def get_fill_perp_order_ix(
        self,
        user_account_pubkey: Pubkey,
        user_account: UserAccount,
        order: Order,
        maker_info: Optional[Union[MakerInfo, list[MakerInfo]]],
        referrer_info: Optional[ReferrerInfo],
    ) -> Instruction:
        user_stats_pubkey = get_user_stats_account_public_key(
            self.program.program_id, user_account.authority
        )

        filler_pubkey = self.get_user_account_public_key()
        filler_stats_pubkey = self.get_user_stats_public_key()

        market_index = (
            order.market_index
            if order
            else next(
                (
                    order.market_index
                    for order in user_account.orders
                    if order.order_id == user_account.next_order_id - 1
                ),
                None,
            )
        )

        maker_info = (
            maker_info
            if isinstance(maker_info, list)
            else [maker_info]
            if maker_info
            else []
        )

        user_accounts = [user_account]
        for maker in maker_info:
            user_accounts.append(maker.maker_user_account)

        remaining_accounts = self.get_remaining_accounts(user_accounts, [market_index])

        for maker in maker_info:
            remaining_accounts.append(
                AccountMeta(pubkey=maker.maker, is_writable=True, is_signer=False)
            )
            remaining_accounts.append(
                AccountMeta(pubkey=maker.maker_stats, is_writable=True, is_signer=False)
            )

        if referrer_info:
            referrer_is_maker = any(
                maker.maker == referrer_info.referrer for maker in maker_info
            )
            if not referrer_is_maker:
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=referrer_info.referrer, is_writable=True, is_signer=False
                    )
                )
                remaining_accounts.append(
                    AccountMeta(
                        pubkey=referrer_info.referrer_stats,
                        is_writable=True,
                        is_signer=False,
                    )
                )

        order_id = order.order_id
        return self.program.instruction["fill_perp_order"](
            order_id,
            None,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "filler": filler_pubkey,
                    "filler_stats": filler_stats_pubkey,
                    "user": user_account_pubkey,
                    "user_stats": user_stats_pubkey,
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    def get_revert_fill_ix(self):
        filler_pubkey = self.get_user_account_public_key()
        filler_stats_pubkey = self.get_user_stats_public_key()

        return self.program.instruction["revert_fill"](
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "filler": filler_pubkey,
                    "filler_stats": filler_stats_pubkey,
                    "authority": self.wallet.payer.pubkey(),
                }
            )
        )

    def get_trigger_order_ix(
        self,
        user_account_pubkey: Pubkey,
        user_account: UserAccount,
        order: Order,
        filler_pubkey: Optional[Pubkey] = None,
    ):
        filler = filler_pubkey or self.get_user_account_public_key()

        if is_variant(order.market_type, "Perp"):
            remaining_accounts = self.get_remaining_accounts(
                user_accounts=[user_account],
                writable_perp_market_indexes=[order.market_index],
            )
        else:
            remaining_accounts = self.get_remaining_accounts(
                user_accounts=[user_account],
                writable_spot_market_indexes=[
                    order.market_index,
                    QUOTE_SPOT_MARKET_INDEX,
                ],
            )

        return self.program.instruction["trigger_order"](
            order.order_id,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "filler": filler,
                    "user": user_account_pubkey,
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def force_cancel_orders(
        self,
        user_account_pubkey: Pubkey,
        user_account: UserAccount,
        filler_pubkey: Optional[Pubkey] = None,
    ) -> Signature:
        tx_sig_and_slot = await self.send_ixs(
            self.get_force_cancel_orders_ix(
                user_account_pubkey, user_account, filler_pubkey
            )
        )

        return tx_sig_and_slot.tx_sig

    def get_force_cancel_orders_ix(
        self,
        user_account_pubkey: Pubkey,
        user_account: UserAccount,
        filler_pubkey: Optional[Pubkey] = None,
    ):
        filler = filler_pubkey or self.get_user_account_public_key()

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[user_account],
            writable_spot_market_indexes=[QUOTE_SPOT_MARKET_INDEX],
        )

        return self.program.instruction["force_cancel_orders"](
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "filler": filler,
                    "user": user_account_pubkey,
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            )
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
            direction=(
                PositionDirection.Long()
                if position.base_asset_amount < 0
                else PositionDirection.Short()
            ),
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
                    "authority": self.wallet.payer.pubkey(),
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
                    "drift_signer": self.get_signer_public_key(self.program_id),
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
        reduce_only: Optional[SwapReduceOnly] = None,
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
        slippage_bps: int = 50,
        quote: Optional[dict] = None,
        reduce_only: Optional[SwapReduceOnly] = None,
        user_account_public_key: Optional[Pubkey] = None,
        swap_mode: str = "ExactIn",
        fee_account: Optional[Pubkey] = None,
        platform_fee_bps: Optional[int] = None,
        only_direct_routes: bool = False,
        max_accounts: int = 50,
    ) -> Tuple[list[Instruction], list[AddressLookupTableAccount]]:
        pre_instructions: list[Instruction] = []
        JUPITER_URL = os.getenv("JUPITER_URL", "https://lite-api.jup.ag/swap/v1")

        out_market = self.get_spot_market_account(out_market_idx)
        in_market = self.get_spot_market_account(in_market_idx)

        if not out_market or not in_market:
            raise Exception("Invalid market indexes")

        if quote is None:
            params = {
                "inputMint": str(in_market.mint),
                "outputMint": str(out_market.mint),
                "amount": str(amount),
                "slippageBps": slippage_bps,
                "swapMode": swap_mode,
                "maxAccounts": max_accounts,
            }
            if only_direct_routes:
                params["onlyDirectRoutes"] = "true"
            if platform_fee_bps:
                params["platformFeeBps"] = platform_fee_bps

            url = f"{JUPITER_URL}/quote?" + "&".join(
                f"{k}={v}" for k, v in params.items()
            )
            quote_resp = requests.get(url)

            if quote_resp.status_code != 200:
                raise Exception(f"Jupiter quote failed: {quote_resp.text}")

            quote = quote_resp.json()

        if out_ata is None:
            out_ata = self.get_associated_token_account_public_key(
                out_market.market_index
            )
            ai = await self.connection.get_account_info(out_ata)
            if not ai.value:
                pre_instructions.append(
                    self.create_associated_token_account_idempotent_instruction(
                        out_ata,
                        self.wallet.public_key,
                        self.wallet.public_key,
                        out_market.mint,
                    )
                )

        if in_ata is None:
            in_ata = self.get_associated_token_account_public_key(
                in_market.market_index
            )
            ai = await self.connection.get_account_info(in_ata)
            if not ai.value:
                pre_instructions.append(
                    self.create_associated_token_account_idempotent_instruction(
                        in_ata,
                        self.wallet.public_key,
                        self.wallet.public_key,
                        in_market.mint,
                    )
                )

        swap_data = {
            "quoteResponse": quote,
            "userPublicKey": str(self.wallet.public_key),
            "destinationTokenAccount": str(out_ata),
        }
        if fee_account:
            swap_data["feeAccount"] = str(fee_account)

        swap_ix_resp = requests.post(
            f"{JUPITER_URL}/swap-instructions",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=swap_data,
        )

        if swap_ix_resp.status_code != 200:
            raise Exception(f"Jupiter swap instructions failed: {swap_ix_resp.text}")

        swap_ix_json = swap_ix_resp.json()
        swap_ix = swap_ix_json.get("swapInstruction")
        address_table_lookups = swap_ix_json.get("addressLookupTableAddresses")

        address_table_lookup_accounts: list[AddressLookupTableAccount] = []

        for table_pubkey in address_table_lookups:
            address_table_lookup_account = await get_address_lookup_table(
                self.connection, Pubkey.from_string(table_pubkey)
            )
            address_table_lookup_accounts.append(address_table_lookup_account)

        drift_lookup_tables = await self.fetch_market_lookup_table_accounts()
        swap_ixs = [swap_ix]

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
        cleansed_ixs: list[Instruction] = []

        for ix in ixs:
            if isinstance(ix, list):
                for i in ix:
                    if isinstance(i, dict):
                        cleansed_ixs.append(self._dict_to_instructions(i))
            elif isinstance(ix, dict):
                cleansed_ixs.append(self._dict_to_instructions(ix))
            else:
                cleansed_ixs.append(ix)

        lookup_tables = [
            *list(address_table_lookup_accounts),
            *list(drift_lookup_tables),
        ]
        return cleansed_ixs, lookup_tables

    def _dict_to_instructions(self, instructions_dict: dict) -> Instruction:
        program_id = Pubkey.from_string(instructions_dict["programId"])
        accounts = [
            AccountMeta(
                Pubkey.from_string(account["pubkey"]),
                account["isSigner"],
                account["isWritable"],
            )
            for account in instructions_dict["accounts"]
        ]
        data = base64.b64decode(instructions_dict["data"])
        return Instruction(program_id, data, accounts)

    def get_perp_market_accounts(self) -> list[PerpMarketAccount]:
        return [
            value.data
            for value in self.account_subscriber.get_market_accounts_and_slots()
            if value is not None
        ]

    def get_spot_market_accounts(self) -> list[SpotMarketAccount]:
        return [
            value.data
            for value in self.account_subscriber.get_spot_market_accounts_and_slots()
            if value is not None
        ]

    def get_market_index_and_type(
        self, name: str
    ) -> Union[Tuple[int, MarketType], None]:
        """
        Returns the market index and type for a given market name \n
        Returns `None` if the market name couldn't be matched \n
        e.g. "SOL-PERP" -> `(0, MarketType.Perp())`
        """
        name = name.upper()
        for perp_market_account in self.get_perp_market_accounts():
            if decode_name(perp_market_account.name).upper() == name:
                return (perp_market_account.market_index, MarketType.Perp())

        for spot_market_account in self.get_spot_market_accounts():
            if decode_name(spot_market_account.name).upper() == name:
                return (spot_market_account.market_index, MarketType.Spot())

        return None  # explicitly return None if no match is found

    def get_update_user_margin_trading_enabled_ix(
        self,
        margin_trading_enabled: bool,
        sub_account_id: Optional[int] = None,
    ) -> Instruction:
        sub_account_id = self.get_sub_account_id_for_ix(sub_account_id)

        remaining_accounts = self.get_remaining_accounts(
            user_accounts=[self.get_user_account(sub_account_id)],
        )

        return self.program.instruction["update_user_margin_trading_enabled"](
            sub_account_id,
            margin_trading_enabled,
            ctx=Context(
                accounts={
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.wallet.payer.pubkey(),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def update_user_margin_trading_enabled(
        self, margin_trading_enabled: bool, sub_account_id: Optional[int] = None
    ) -> Signature:
        """Toggles margin trading for a user

        Args:
            sub_account_id (int, optional): subaccount id. Defaults to 0.

        Returns:
            Signature: tx sig
        """
        await self.add_user(sub_account_id)

        tx_sig = (
            await self.send_ixs(
                [
                    self.get_update_user_margin_trading_enabled_ix(
                        margin_trading_enabled=margin_trading_enabled,
                        sub_account_id=sub_account_id,
                    )
                ]
            )
        ).tx_sig
        return tx_sig

    async def update_prelaunch_oracle(
        self,
        market_index: int,
    ):
        return (
            await self.send_ixs(
                self.get_update_prelaunch_oracle_ix(
                    market_index,
                ),
            )
        ).tx_sig

    def get_update_prelaunch_oracle_ix(self, market_index: int):
        perp_market = self.get_perp_market_account(market_index)

        if not is_variant(perp_market.amm.oracle_source, "Prelaunch"):
            raise ValueError(f"wrong oracle source: {perp_market.amm.oracle_source}")

        return self.program.instruction["update_prelaunch_oracle"](
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "perp_market": perp_market.pubkey,
                    "oracle": perp_market.amm.oracle,
                }
            )
        )

    async def init_sequence(self, subaccount: int = 0) -> Signature:
        try:
            sig = (await self.send_ixs([self.get_sequence_init_ix(subaccount)])).tx_sig
            self.sequence_initialized_by_subaccount[subaccount] = True
            return sig
        except Exception as e:
            print(f"WARNING: failed to initialize sequence: {e}")

    def get_sequence_init_ix(self, subaccount: int = 0) -> Instruction:
        if self.enforce_tx_sequencing is False:
            raise ValueError("tx sequencing is disabled")
        return self.sequence_enforcer_program.instruction["initialize"](
            self.sequence_bump_by_subaccount[subaccount],
            str(subaccount),
            ctx=Context(
                accounts={
                    "sequence_account": self.sequence_address_by_subaccount[subaccount],
                    "authority": self.wallet.payer.pubkey(),
                    "system_program": ID,
                }
            ),
        )

    async def reset_sequence_number(
        self, sequence_number: int = 0, subaccount: int = 0
    ) -> Signature:
        try:
            ix = self.get_reset_sequence_number_ix(sequence_number)
            self.resetting_sequence = True
            sig = (await self.send_ixs(ix)).tx_sig
            self.resetting_sequence = False
            self.sequence_number_by_subaccount[subaccount] = sequence_number
            return sig
        except Exception as e:
            print(f"WARNING: failed to reset sequence number: {e}")

    def get_reset_sequence_number_ix(
        self, sequence_number: int, subaccount: int = 0
    ) -> Instruction:
        if self.enforce_tx_sequencing is False:
            raise ValueError("tx sequencing is disabled")
        return self.sequence_enforcer_program.instruction["reset_sequence_number"](
            sequence_number,
            ctx=Context(
                accounts={
                    "sequence_account": self.sequence_address_by_subaccount[subaccount],
                    "authority": self.wallet.payer.pubkey(),
                }
            ),
        )

    def get_check_and_set_sequence_number_ix(
        self, sequence_number: Optional[int] = None, subaccount: int = 0
    ):
        if self.enforce_tx_sequencing is False:
            raise ValueError("tx sequencing is disabled")
        sequence_number = (
            sequence_number or self.sequence_number_by_subaccount[subaccount]
        )

        if (
            sequence_number < self.sequence_number_by_subaccount[subaccount] - 1
        ):  # we increment after creating the ix, so we check - 1
            print(
                f"WARNING: sequence number {sequence_number} < last used {self.sequence_number_by_subaccount[subaccount] - 1}"
            )

        ix = self.sequence_enforcer_program.instruction[
            "check_and_set_sequence_number"
        ](
            sequence_number,
            ctx=Context(
                accounts={
                    "sequence_account": self.sequence_address_by_subaccount[subaccount],
                    "authority": self.wallet.payer.pubkey(),
                }
            ),
        )

        self.sequence_number_by_subaccount[subaccount] += 1
        return ix

    async def load_sequence_info(self):
        for subaccount in self.sub_account_ids:
            address, bump = get_sequencer_public_key_and_bump(
                self.sequence_enforcer_pid, self.wallet.payer.pubkey(), subaccount
            )
            try:
                sequence_account_raw = await self.sequence_enforcer_program.account[
                    "SequenceAccount"
                ].fetch(address)
            except anchorpy.error.AccountDoesNotExistError:
                self.sequence_address_by_subaccount[subaccount] = address
                self.sequence_number_by_subaccount[subaccount] = 1
                self.sequence_bump_by_subaccount[subaccount] = bump
                self.sequence_initialized_by_subaccount[subaccount] = False
                continue
            sequence_account = cast(SequenceAccount, sequence_account_raw)
            self.sequence_number_by_subaccount[subaccount] = (
                sequence_account.sequence_num + 1
            )
            self.sequence_bump_by_subaccount[subaccount] = bump
            self.sequence_initialized_by_subaccount[subaccount] = True
            self.sequence_address_by_subaccount[subaccount] = address

    async def update_user_protected_maker_orders(
        self,
        sub_account_id: int,
        protected_orders: bool,
    ):
        return (
            await self.send_ixs(
                [
                    await self.get_update_user_protected_maker_orders_ix(
                        sub_account_id, protected_orders
                    )
                ]
            )
        ).tx_sig

    async def get_update_user_protected_maker_orders_ix(
        self,
        sub_account_id: int,
        protected_orders: bool,
    ):
        return self.program.instruction["update_user_protected_maker_orders"](
            sub_account_id,
            protected_orders,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(sub_account_id),
                    "authority": self.wallet.payer.pubkey(),
                    "protected_maker_mode_config": get_protected_maker_mode_config_public_key(
                        self.program_id
                    ),
                }
            ),
        )
