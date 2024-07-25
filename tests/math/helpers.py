import asyncio
from copy import deepcopy

from solders.pubkey import Pubkey  # type: ignore
from solders.keypair import Keypair  # type: ignore

from anchorpy import Wallet

from solana.rpc.async_api import AsyncClient
from driftpy.constants.numeric_constants import PRICE_PRECISION

from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.types import (
    OraclePriceData,
    UserAccount,
    PerpPosition,
    SpotPosition,
    Order,
    SpotBalanceType,
    OrderStatus,
    OrderType,
    MarketType,
    PositionDirection,
    OrderTriggerCondition,
)

mock_perp_position = PerpPosition(
    base_asset_amount=0,
    last_cumulative_funding_rate=0,
    market_index=0,
    quote_asset_amount=0,
    quote_break_even_amount=0,
    quote_entry_amount=0,
    open_orders=0,
    open_bids=0,
    open_asks=0,
    settled_pnl=0,
    lp_shares=0,
    remainder_base_asset_amount=0,
    last_base_asset_amount_per_lp=0,
    last_quote_asset_amount_per_lp=0,
    per_lp_base=0,
)

mock_spot_position = SpotPosition(
    market_index=0,
    balance_type=SpotBalanceType.Deposit(),
    scaled_balance=0,
    open_orders=0,
    open_bids=0,
    open_asks=0,
    cumulative_deposits=0,
    padding=[0, 0, 0, 0],
)

mock_order = Order(
    status=0,
    order_type=OrderType.Market(),
    market_type=MarketType.Perp(),
    slot=0,
    order_id=0,
    user_order_id=0,
    market_index=0,
    price=0,
    base_asset_amount=0,
    base_asset_amount_filled=0,
    quote_asset_amount_filled=0,
    direction=0,
    reduce_only=False,
    trigger_price=0,
    trigger_condition=OrderTriggerCondition.Above(),
    existing_position_direction=PositionDirection.Long(),
    post_only=False,
    immediate_or_cancel=False,
    oracle_price_offset=0,
    auction_duration=0,
    auction_start_price=0,
    auction_end_price=0,
    max_ts=0,
    padding=[0, 0, 0],
)

mock_user_account = UserAccount(
    authority=Pubkey.default(),
    delegate=Pubkey.default(),
    sub_account_id=0,
    name=[1],
    spot_positions=[deepcopy(mock_spot_position) for _ in range(8)],
    perp_positions=[deepcopy(mock_perp_position) for _ in range(8)],
    orders=[deepcopy(mock_order) for _ in range(8)],
    last_add_perp_lp_shares_ts=0,
    status=0,
    next_liquidation_id=0,
    next_order_id=0,
    max_margin_ratio=0,
    settled_perp_pnl=0,
    total_deposits=0,
    total_withdraws=0,
    total_social_loss=0,
    cumulative_perp_funding=0,
    cumulative_spot_fees=0,
    liquidation_margin_freed=0,
    last_active_slot=0,
    is_margin_trading_enabled=True,
    idle=False,
    open_orders=0,
    has_open_order=False,
    open_auctions=0,
    has_open_auction=False,
    last_fuel_bonus_update_ts=0,
    padding=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
)


class MockUserMap:
    def __init__(self):
        self.user_map = {}
        self.drift_client = DriftClient(
            AsyncClient("http://localhost:8899"),
            wallet=Wallet(Keypair()),
        )

    async def add_pubkey(self, pubkey: Pubkey):
        user = DriftUser(
            self.drift_client,
            pubkey,
        )
        self.user_map[str(pubkey)] = user

    async def must_get(self, _: str) -> DriftUser:
        return DriftUser(self.drift_client, Pubkey.default())


async def make_mock_user(
    mock_perp_markets,
    mock_spot_markets,
    mock_user_account,
    perp_oracle_price_list,
    spot_oracle_price_list,
):
    umap = MockUserMap()
    muser: DriftUser = await umap.must_get("")
    oracle_price_map = {}

    for i in range(len(mock_perp_markets)):
        oracle_price_map[str(mock_perp_markets[i].amm.oracle)] = perp_oracle_price_list[
            i
        ]

    for i in range(len(mock_spot_markets)):
        oracle_price_map[str(mock_spot_markets[i].oracle)] = spot_oracle_price_list[i]

    def get_user():
        return mock_user_account

    def get_perp(idx):
        return mock_perp_markets[idx]

    def get_spot(idx):
        return mock_spot_markets[idx]

    def get_oracle(key):
        return OraclePriceData(
            price=(oracle_price_map[str(key)] * PRICE_PRECISION),
            slot=0,
            confidence=1,
            twap=0,
            twap_confidence=0,
            has_sufficient_number_of_data_points=True,
        )

    def get_oracle_price_data_for_perp_market(market_index):
        market = get_perp(market_index)
        return get_oracle(market.amm.oracle)

    def get_oracle_price_data_for_spot_market(market_index):
        market = get_spot(market_index)
        return get_oracle(market.oracle)

    muser.get_user_account = get_user
    muser.drift_client.get_perp_market_account = get_perp
    muser.drift_client.get_spot_market_account = get_spot
    muser.drift_client.get_oracle_price_data = get_oracle
    muser.drift_client.get_oracle_price_data_for_perp_market = (
        get_oracle_price_data_for_perp_market
    )
    muser.drift_client.get_oracle_price_data_for_spot_market = (
        get_oracle_price_data_for_spot_market
    )

    return muser


async def looper(condition):
    tries = 0
    while tries < 50:
        if condition():
            return True
        print("Retrying")
        await asyncio.sleep(1)
        tries += 1
    return False
