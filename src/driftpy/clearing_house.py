from dataclasses import dataclass
from solana.publickey import PublicKey
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
from pathlib import Path

import driftpy
from driftpy.constants.numeric_constants import QUOTE_ASSET_BANK_INDEX
from driftpy.addresses import *
from driftpy.sdk_types import *
from driftpy.types import *
from driftpy.accounts import *

from anchorpy import Wallet
from driftpy.constants.config import Config
from anchorpy import Provider

from typing import Union, Optional, Dict, List, Any, Sequence, cast
from driftpy.math.positions import is_available, is_spot_position_available

DEFAULT_USER_NAME = "Main Account"


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
        self.signers = [self.signer]
        self.usdc_ata = None

    @staticmethod
    def from_config(config: Config, provider: Provider, authority: Keypair = None):
        # read the idl
        file = Path(str(driftpy.__path__[0]) + "/idl/clearing_house.json")
        with file.open() as f:
            idl_dict = json.load(f)
        idl = Idl.from_json(idl_dict)

        # create the program
        program = Program(
            idl,
            config.clearing_house_program_id,
            provider,
        )

        clearing_house = ClearingHouse(program, authority)

        clearing_house.config = config
        clearing_house.idl = idl

        return clearing_house

    def get_user_account_public_key(self, user_id=0) -> PublicKey:
        return get_user_account_public_key(self.program_id, self.authority, user_id)

    async def get_user(self, user_id=0) -> User:
        return await get_user_account(self.program, self.authority, user_id)

    def get_state_public_key(self):
        return get_state_public_key(self.program_id)

    def get_user_stats_public_key(self):
        return get_user_stats_account_public_key(self.program_id, self.authority)

    async def send_ixs(self, ixs: Union[TransactionInstruction, list[TransactionInstruction]], signers=None):
        if isinstance(ixs, TransactionInstruction):
            ixs = [ixs]

        tx = Transaction()
        for ix in ixs:
            tx.add(ix)

        if signers is None:
            signers = self.signers

        return await self.program.provider.send(tx, signers=signers)

    async def intialize_user(self, user_id: int = 0):
        ixs = []
        if user_id == 0:
            ixs.append(self.get_initialize_user_stats())
        ix = self.get_initialize_user_instructions(user_id)
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
                    "rent": SYSVAR_RENT_PUBKEY,
                    "system_program": SYS_PROGRAM_ID,
                },
            ),
        )

    def get_initialize_user_instructions(
        self, user_id: int = 0, name: str = DEFAULT_USER_NAME
    ) -> TransactionInstruction:
        user_public_key = self.get_user_account_public_key(user_id)
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
            user_id,
            name_byte_array,
            ctx=Context(
                accounts={
                    "user": user_public_key,
                    "user_stats": user_stats_public_key,
                    "state": state_public_key,
                    "authority": self.authority,
                    "payer": self.authority,
                    "rent": SYSVAR_RENT_PUBKEY,
                    "system_program": SYS_PROGRAM_ID,
                },
            ),
        )
        return initialize_user_account_ix

    async def get_remaining_accounts(
        self,
        writable_market_index: int = None,
        writable_spot_market_index: int = None,
        user_id=0,
        include_oracles: bool = True,
        include_spot_markets: bool = True,
        authority: Optional[Union[PublicKey, Sequence[PublicKey]]] = None,
    ):
        if authority is None:
            authority = [self.authority]
        elif isinstance(authority, PublicKey):
            authority = [authority]

        accounts = []
        for pk in authority:
            user_account = await get_user_account(self.program, pk, user_id)
            accounts.append(user_account)

        oracle_map = {}
        spot_market_map = {}
        market_map = {}

        async def track_market(market_index, is_writable):
            market = await get_perp_market_account(self.program, market_index)
            market_map[market_index] = AccountMeta(
                pubkey=market.pubkey,
                is_signer=False,
                is_writable=is_writable,
            )

            if include_oracles:
                oracle_map[str(market.pubkey)] = AccountMeta(
                    pubkey=market.amm.oracle, is_signer=False, is_writable=False
                )

        async def track_spot_market(spot_market_index, is_writable):
            spot_market = await get_spot_market_account(self.program, spot_market_index)
            spot_market_map[spot_market_index] = AccountMeta(
                pubkey=spot_market.pubkey,
                is_signer=False,
                is_writable=is_writable,
            )

            if spot_market_index != 0 and include_oracles:
                oracle_map[str(spot_market.pubkey)] = AccountMeta(
                    pubkey=spot_market.oracle, is_signer=False, is_writable=False
                )

        for user_account in accounts:
            for position in user_account.perp_positions:
                if not is_available(position):
                    market_index = position.market_index
                    await track_market(market_index, is_writable=True)

            if writable_market_index is not None:
                await track_market(writable_market_index, is_writable=True)

            if include_spot_markets:
                for spot_market_balance in user_account.spot_positions:
                    if not is_spot_position_available(spot_market_balance):
                        await track_spot_market(
                            spot_market_balance.market_index, is_writable=False
                        )

                if writable_spot_market_index is not None:
                    await track_spot_market(
                        writable_spot_market_index, is_writable=True
                    )

        remaining_accounts = [
            *oracle_map.values(),
            *spot_market_map.values(),
            *market_map.values(),
        ]

        return remaining_accounts

    async def withdraw(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: PublicKey,
        reduce_only: bool = False,
    ):
        return await self.send_ixs(
            [
                await self.get_withdraw_collateral_ix(
                    amount, spot_market_index, user_token_account, reduce_only
                )
            ]
        )

    async def get_withdraw_collateral_ix(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: PublicKey,
        reduce_only: bool = False,
    ):

        spot_market = await get_spot_market_account(self.program, spot_market_index)
        remaining_accounts = await self.get_remaining_accounts(
            writable_spot_market_index=spot_market_index
        )
        ch_signer = get_clearing_house_signer_public_key(self.program_id)

        return self.program.instruction["withdraw"](
            spot_market_index,
            amount,
            reduce_only,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "spot_market": spot_market.pubkey,
                    "spot_market_vault": spot_market.vault,
                    "clearing_house_signer": ch_signer,
                    "user": self.get_user_account_public_key(),
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
        user_token_account: PublicKey,
        user_id: int = 0,
        reduce_only=False,
        user_initialized=True,
    ):
        return await self.send_ixs(
            [
                await self.get_deposit_collateral_ix(
                    amount,
                    spot_market_index,
                    user_token_account,
                    user_id,
                    reduce_only,
                    user_initialized,
                )
            ]
        )

    async def get_deposit_collateral_ix(
        self,
        amount: int,
        spot_market_index: int,
        user_token_account: PublicKey,
        user_id: int = 0,
        reduce_only=False,
        user_initialized=True,
    ) -> TransactionInstruction:

        if user_initialized:
            remaining_accounts = await self.get_remaining_accounts(
                writable_spot_market_index=spot_market_index
            )
        else:
            raise Exception("not implemented...")

        spot_market_pk = get_spot_market_public_key(
            self.program_id, spot_market_index
        )
        spot_vault_public_key = get_spot_market_vault_public_key(
            self.program_id, spot_market_index
        )
        user_account_public_key = get_user_account_public_key(
            self.program_id, self.authority, user_id
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

    async def add_liquidity(self, amount: int, market_index: int, user_id: int = 0):
        return await self.send_ixs(
            [await self.get_add_liquidity_ix(amount, market_index, user_id)]
        )

    async def get_add_liquidity_ix(
        self, amount: int, market_index: int, user_id: int = 0
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index
        )
        user_account_public_key = get_user_account_public_key(
            self.program_id, self.authority, user_id
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

    async def remove_liquidity(self, amount: int, market_index: int, user_id: int = 0):
        return await self.send_ixs(
            [await self.get_remove_liquidity_ix(amount, market_index, user_id)]
        )

    async def get_remove_liquidity_ix(
        self, amount: int, market_index: int, user_id: int = 0
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index,
        )
        user_account_public_key = self.get_user_account_public_key(user_id)

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
    
    async def cancel_orders(
        self,
    ): 
        remaining_accounts = await self.get_remaining_accounts()

        return self.program.instruction["cancel_orders"](
            None,
            None,
            None,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(),
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )


    async def cancel_order(
        self, 
        order_id: Optional[int] = None
    ):
        return await self.send_ixs(
            await self.get_cancel_order_ix(order_id),
        )

    async def get_cancel_order_ix(
        self, 
        order_id: Optional[int] = None
    ):
        remaining_accounts = await self.get_remaining_accounts()

        return self.program.instruction["cancel_order"](
            order_id,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": self.get_user_account_public_key(),
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
        limit_price: int = 0,
        ioc: bool = False,
    ):
        return await self.send_ixs(
            await self.get_open_position_ix(direction, amount, market_index, limit_price, ioc),
        )

    async def get_open_position_ix(
        self, 
        direction: PositionDirection,
        amount: int,
        market_index: int,
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

        ix = await self.get_place_and_take_ix(order)
        return ix

    def get_increase_compute_ix(self) -> TransactionInstruction:
        program_id = PublicKey("ComputeBudget111111111111111111111111111111")

        name_bytes = bytearray(1 + 4 + 4)
        pack_into("B", name_bytes, 0, 0)
        pack_into("I", name_bytes, 1, 500_000)
        pack_into("I", name_bytes, 5, 0)
        data = bytes(name_bytes)

        compute_ix = TransactionInstruction([], program_id, data)

        return compute_ix

    async def place_order(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
    ):
        return await self.send_ixs(
            await self.get_place_order_ix(order_params, maker_info),
        )

    async def get_place_order_ix(
        self,
        order_params: OrderParams,
    ):
        user_account_public_key = self.get_user_account_public_key()

        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=order_params.market_index,
        )

        ix = self.program.instruction["place_order"](
            order_params,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": user_account_public_key,
                    "authority": self.authority,
                },
                remaining_accounts=remaining_accounts,
            ),
        )

        return [
            self.get_increase_compute_ix(),
            ix
        ]

    async def place_and_take(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
    ):
        return await self.send_ixs(
            await self.get_place_and_take_ix(order_params, maker_info),
        )

    async def get_place_and_take_ix(
        self,
        order_params: OrderParams,
        maker_info: MakerInfo = None,
    ):
        user_account_public_key = self.get_user_account_public_key()

        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=order_params.market_index,
            writable_spot_market_index=QUOTE_ASSET_BANK_INDEX,
        )

        maker_order_id = None
        if maker_info is not None:
            maker_order_id = maker_info.order.order_id
            remaining_accounts.append(
                AccountMeta(pubkey=maker_info.maker, is_signer=False, is_writable=True)
            )

        return [
            self.get_increase_compute_ix(),
            self.program.instruction["place_and_take_perp_order"](
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
                )
            )
        ]

    async def settle_lp(
        self,
        settlee_authority: PublicKey,
        market_index: int,
    ):
        return await self.send_ixs(
            [await self.get_settle_lp_ix(settlee_authority, market_index)], signers=[]
        )

    async def get_settle_lp_ix(
        self,
        settlee_authority: PublicKey,
        market_index: int,
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index,
            authority=settlee_authority,
        )

        return self.program.instruction["settle_lp"](
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "user": get_user_account_public_key(
                        self.program_id, settlee_authority
                    ),
                },
                remaining_accounts=remaining_accounts,
            ),
        )

    async def get_user_position(
        self,
        market_index: int,
    ) -> Optional[PerpPosition]:
        user = await get_user_account(self.program, self.authority)

        found = False
        for position in user.perp_positions:
            if position.market_index == market_index and not is_available(position):
                found = True
                break

        if not found:
            return None

        # assert position.market_index == market_index, "no position in market"
        return position

    async def close_position(
        self,
        market_index: int,
        limit_price: int = 0,
    ):
        return await self.send_ixs(
            await self.get_close_position_ix(
                market_index, limit_price,
            )
        )

    async def get_close_position_ix(
        self,
        market_index: int,
        limit_price: int = 0,
    ):
        position = await self.get_user_position(market_index)
        if position is None or position.base_asset_amount == 0:
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

        ix = await self.get_place_and_take_ix(order)
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
            post_only=False,
            immediate_or_cancel=False,
            trigger_price=0,
            trigger_condition=OrderTriggerCondition.ABOVE(),
            oracle_price_offset=0,
            auction_duration=None,
            max_ts=None,
            auction_start_price=None,
            auction_end_price=None,
        )

    async def liquidate_perp(
        self,
        user_authority: PublicKey,
        market_index: int,
        max_base_asset_amount: int,
        limit_price: Optional[int] = None
    ):
        return await self.send_ixs(
            [
                await self.get_liquidate_perp_ix(
                    user_authority,
                    market_index,
                    max_base_asset_amount,
                    limit_price,
                )
            ]
        )

    async def get_liquidate_perp_ix(
        self,
        user_authority: PublicKey,
        market_index: int,
        max_base_asset_amount: int,
        limit_price: Optional[int] = None
    ):
        user_pk = get_user_account_public_key(self.program_id, user_authority)
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key()
        liq_stats_pk = self.get_user_stats_public_key()

        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index, authority=user_authority
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


    async def get_liquidate_perp_pnl_for_deposit_ix(
        self, 
        user_authority: PublicKey,
        perp_market_index: int,
        spot_market_index: int,
        max_pnl_transfer: int,
    ):
        user_pk = get_user_account_public_key(self.program_id, user_authority)
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key()
        liq_stats_pk = self.get_user_stats_public_key()

        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=perp_market_index, 
            writable_spot_market_index=spot_market_index,
            authority=user_authority
        )

        result = self.program.instruction["liquidate_perp_pnl_for_deposit"](
            perp_market_index,
            spot_market_index,
            max_pnl_transfer,
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

    async def liquidate_perp_pnl_for_deposit(
        self, 
        user_authority: PublicKey,
        perp_market_index: int,
        spot_market_index: int,
        max_pnl_transfer: int,
    ):
        return await self.send_ixs(
            self.get_liquidate_perp_pnl_for_deposit_ix(
                user_authority,
                perp_market_index,
                spot_market_index,
                max_pnl_transfer,
            )
        )

    async def settle_pnl(
        self,
        user_authority: PublicKey,
        market_index: int,
    ):
        return await self.send_ixs(
            [
                await self.get_settle_pnl_ix(
                    user_authority,
                    market_index,
                )
            ]
        )

    async def get_settle_pnl_ix(
        self,
        user_authority: PublicKey,
        market_index: int,
    ):
        remaining_accounts = await self.get_remaining_accounts(
            authority=user_authority,
            writable_market_index=market_index,
            writable_spot_market_index=QUOTE_ASSET_BANK_INDEX,
        )

        return [
            self.get_increase_compute_ix(),
            self.program.instruction["settle_pnl"](
                market_index,
                ctx=Context(
                    accounts={
                        "state": self.get_state_public_key(),
                        "authority": self.authority,
                        "user": get_user_account_public_key(self.program_id, user_authority),
                        "spot_market_vault": get_spot_market_vault_public_key(self.program_id, QUOTE_ASSET_BANK_INDEX),
                    },
                    remaining_accounts=remaining_accounts,
                ),
            ), 
        ]

    async def resolve_perp_bankruptcy(
        self,
        user_authority: PublicKey,
        market_index: int,
    ):
        return await self.send_ixs(
            [
                await self.get_resolve_perp_bankruptcy_ix(
                    user_authority,
                    market_index,
                )
            ]
        )

    async def get_resolve_perp_bankruptcy_ix(
        self,
        user_authority: PublicKey,
        market_index: int,
    ):
        user_pk = get_user_account_public_key(self.program_id, user_authority)
        user_stats_pk = get_user_stats_account_public_key(
            self.program_id,
            user_authority,
        )

        liq_pk = self.get_user_account_public_key()
        liq_stats_pk = self.get_user_stats_public_key()

        remaining_accounts = await self.get_remaining_accounts(
            writable_market_index=market_index,
            writable_spot_market_index=QUOTE_ASSET_BANK_INDEX,
            authority=[user_authority, self.authority],
        )

        spot_market = await get_spot_market_account(
            self.program, QUOTE_ASSET_BANK_INDEX
        )
        ch_signer = get_clearing_house_signer_public_key(self.program_id)

        return self.program.instruction["resolve_perp_bankruptcy"](
            QUOTE_ASSET_BANK_INDEX,
            market_index,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "authority": self.authority,
                    "user": user_pk,
                    "user_stats": user_stats_pk,
                    "liquidator": liq_pk,
                    "liquidator_stats": liq_stats_pk,
                    "spot_market_vault": spot_market.vault,
                    "insurance_fund_vault": spot_market.insurance_fund.vault,
                    "clearing_house_signer": ch_signer,
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
                await self.get_settle_expired_market_ix(
                    market_index,
                )
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

        spot_pk = get_spot_market_public_key(self.program_id, QUOTE_ASSET_BANK_INDEX)
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
        self,
        spot_market_index: int, 
        amount: int
    ):
        return await self.send_ixs(
            await self.get_request_remove_insurance_fund_stake_ix(spot_market_index, amount)
        )
    
    async def get_request_remove_insurance_fund_stake_ix(
        self,
        spot_market_index: int, 
        amount: int,
    ):
        ra = await self.get_remaining_accounts(
            writable_spot_market_index=spot_market_index
        )

        return self.program.instruction["request_remove_insurance_fund_stake"](
            spot_market_index,
            amount,
            ctx=Context(
                accounts={
                    "spot_market": get_spot_market_public_key(self.program_id, spot_market_index),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(self.program_id, self.authority, spot_market_index),
                    "user_stats": get_user_stats_account_public_key(self.program_id, self.authority),
                    "authority": self.authority,
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(self.program_id, spot_market_index),
                },
                remaining_accounts=ra
            ),
        )
    
    async def remove_insurance_fund_stake(
        self, 
        spot_market_index: int
    ):
        return await self.send_ixs(
            await self.get_remove_insurance_fund_stake_ix(
                spot_market_index
            )
        )

    async def get_remove_insurance_fund_stake_ix(
        self, 
        spot_market_index: int
    ):
        ra = await self.get_remaining_accounts(writable_spot_market_index=spot_market_index)

        return self.program.instruction["remove_insurance_fund_stake"](
            spot_market_index,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(self.program_id, spot_market_index),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(self.program_id, self.authority, spot_market_index),
                    "user_stats": get_user_stats_account_public_key(self.program_id, self.authority),
                    "authority": self.authority,
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(self.program_id, spot_market_index),
                    "clearing_house_signer": get_clearing_house_signer_public_key(self.program_id), 
                    "user_token_account": self.usdc_ata,
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=ra
            ),
        )
    
    async def add_insurance_fund_stake(
        self,
        spot_market_index: int, 
        amount: int
    ):
        return await self.send_ixs(
            await self.get_add_insurance_fund_stake_ix(spot_market_index, amount)
        )
    
    async def get_add_insurance_fund_stake_ix(
        self,
        spot_market_index: int, 
        amount: int,
    ):
        remaining_accounts = await self.get_remaining_accounts(
            writable_spot_market_index=spot_market_index,
        )

        assert self.usdc_ata is not None, 'please set self.usdc_ata as your usdc ata pubkey before this ix'
        return self.program.instruction["add_insurance_fund_stake"](
            spot_market_index,
            amount,
            ctx=Context(
                accounts={
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(self.program_id, spot_market_index),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(self.program_id, self.authority, spot_market_index),
                    "user_stats": get_user_stats_account_public_key(self.program_id, self.authority),
                    "authority": self.authority,
                    "spot_market_vault": get_spot_market_vault_public_key(self.program_id, spot_market_index),
                    "insurance_fund_vault": get_insurance_fund_vault_public_key(self.program_id, spot_market_index),
                    "clearing_house_signer": get_clearing_house_signer_public_key(self.program_id), 
                    "user_token_account": self.usdc_ata, 
                    "token_program": TOKEN_PROGRAM_ID,
                },
                remaining_accounts=remaining_accounts
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
                    "spot_market": get_spot_market_public_key(self.program_id, spot_market_index),
                    "insurance_fund_stake": get_insurance_fund_stake_public_key(self.program_id, self.authority, spot_market_index),
                    "user_stats": get_user_stats_account_public_key(self.program_id, self.authority),
                    "state": get_state_public_key(self.program_id),
                    "authority": self.authority,
                    "payer": self.authority, 
                    "rent": SYSVAR_RENT_PUBKEY, 
                    "system_program": SYS_PROGRAM_ID,
                }
            ),
        )