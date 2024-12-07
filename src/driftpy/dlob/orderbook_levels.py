from abc import ABC, abstractmethod
import copy
from datetime import datetime
from typing import Dict, Generator, List, Optional
from solders.pubkey import Pubkey

from driftpy.constants.numeric_constants import BASE_PRECISION, QUOTE_PRECISION
from driftpy.dlob.dlob_node import DLOBNode
from driftpy.math.amm import (
    calculate_amm_reserves_after_swap,
    calculate_market_open_bid_ask,
    calculate_quote_asset_amount_swapped,
    calculate_spread_reserves,
    calculate_updated_amm,
)
from driftpy.math.orders import standardize_price
from driftpy.types import (
    AssetType,
    OraclePriceData,
    PerpMarketAccount,
    PositionDirection,
    SwapDirection,
    is_variant,
)

LiquiditySource = ["serum", "vamm", "dlob", "phoenix"]


class L2Level:
    def __init__(self, price: int, size: int, sources: Dict[str, int]):
        self.price = price
        self.size = size
        self.sources = sources


class L2OrderBook:
    def __init__(
        self, asks: List[L2Level], bids: List[L2Level], slot: Optional[int] = None
    ):
        self.asks = asks
        self.bids = bids
        self.slot = slot


class L3Level:
    def __init__(self, price: int, size: int, maker: Pubkey, order_id: int):
        self.price = price
        self.size = size
        self.maker = maker
        self.order_id = order_id


class L3OrderBook:
    def __init__(
        self, asks: List[L3Level], bids: List[L3Level], slot: Optional[int] = None
    ):
        self.asks = asks
        self.bids = bids
        self.slot = slot


class L2OrderBookGenerator(ABC):
    @abstractmethod
    def get_l2_asks(self) -> Generator[L2Level, None, None]:
        pass

    @abstractmethod
    def get_l2_bids(self) -> Generator[L2Level, None, None]:
        pass


DEFAULT_TOP_OF_BOOK_QUOTE_AMOUNTS = [
    500 * QUOTE_PRECISION,
    1000 * QUOTE_PRECISION,
    2000 * QUOTE_PRECISION,
    5000 * QUOTE_PRECISION,
]


def get_l2_generator_from_dlob_nodes(
    dlob_nodes: Generator[DLOBNode, None, None],
    oracle_price_data: OraclePriceData,
    slot: int,
) -> Generator[L2Level, None, None]:
    for dlob_node in dlob_nodes:
        size = (
            dlob_node.order.base_asset_amount - dlob_node.order.base_asset_amount_filled
        )
        yield L2Level(
            size=size,
            price=dlob_node.get_price(oracle_price_data, slot),
            sources={"dlob": size},
        )


def merge_l2_level_generators(
    l2_level_generators: List[Generator[L2Level, None, None]], compare: callable
) -> Generator[L2Level, None, None]:
    generators = [
        {"generator": gen, "next": next(gen, None)} for gen in l2_level_generators
    ]

    while True:
        next_gen = None
        for gen in generators:
            if gen["next"] is None:
                continue
            if next_gen is None or compare(gen["next"], next_gen["next"]):
                next_gen = gen

        if next_gen is None:
            break

        yield next_gen["next"]
        next_gen["next"] = next(next_gen["generator"], None)


def create_l2_levels(
    generator: Generator[L2Level, None, None], depth: int
) -> List[L2Level]:
    levels: List[L2Level] = []
    for level in generator:
        price = level.price
        size = level.size
        if levels and levels[-1].price == price:
            current_level = levels[-1]
            current_level.size += size
            for source, size in level.sources.items():
                if source in current_level.sources:
                    current_level.sources[source] += size
                else:
                    current_level.sources[source] = size
        elif len(levels) == depth:
            break
        else:
            levels.append(level)

    return levels


def get_vamm_l2_generator(
    market_account: PerpMarketAccount,
    oracle_price_data: OraclePriceData,
    num_orders: int,
    now: Optional[int] = None,
    top_of_book_quote_amounts: Optional[List[int]] = None,
):
    num_base_orders = num_orders
    if top_of_book_quote_amounts:
        num_base_orders = num_orders - len(top_of_book_quote_amounts)
        assert len(top_of_book_quote_amounts) < num_orders

    updated_amm = calculate_updated_amm(market_account.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    min_order_size = market_account.amm.min_order_size
    if open_bids < min_order_size * 2:
        open_bids = 0

    if abs(open_asks) < min_order_size * 2:
        open_asks = 0

    now = now or int(datetime.now().timestamp())
    bid_reserves, ask_reserves = calculate_spread_reserves(
        updated_amm,
        oracle_price_data,
        now,
        is_variant(market_account.contract_type, "Prediction"),
    )

    num_bids = 0
    top_of_book_bid_size = 0
    bid_size = open_bids // num_base_orders

    bid_amm = copy.deepcopy(updated_amm)
    bid_amm.base_asset_reserve = bid_reserves[0]
    bid_amm.quote_asset_reserve = bid_reserves[1]

    def get_l2_bids():
        nonlocal num_bids, top_of_book_bid_size, bid_size, bid_amm
        while num_bids < num_orders and bid_size > 0:
            quote_swapped = 0
            base_swapped = 0

            if top_of_book_quote_amounts and num_bids < len(top_of_book_quote_amounts):
                remaining_base_liquidity = open_bids - top_of_book_bid_size
                quote_swapped = top_of_book_quote_amounts[num_bids]
                (
                    after_swap_quote_reserves,
                    after_swap_base_reserves,
                ) = calculate_amm_reserves_after_swap(
                    bid_amm, AssetType.QUOTE(), quote_swapped, SwapDirection.Remove()
                )
                base_swapped = abs(
                    bid_amm.base_asset_reserve - after_swap_base_reserves
                )

                if remaining_base_liquidity < base_swapped:
                    base_swapped = remaining_base_liquidity
                    (
                        after_swap_quote_reserves,
                        after_swap_base_reserves,
                    ) = calculate_amm_reserves_after_swap(
                        bid_amm, AssetType.BASE(), base_swapped, SwapDirection.Add()
                    )
                    quote_swapped = calculate_quote_asset_amount_swapped(
                        abs(bid_amm.quote_asset_reserve - after_swap_quote_reserves),
                        bid_amm.peg_multiplier,
                        SwapDirection.Add(),
                    )

                top_of_book_bid_size += base_swapped
                bid_size = (open_bids - top_of_book_bid_size) // num_base_orders

            else:
                base_swapped = bid_size
                (
                    after_swap_quote_reserves,
                    after_swap_base_reserves,
                ) = calculate_amm_reserves_after_swap(
                    bid_amm, AssetType.BASE(), base_swapped, SwapDirection.Add()
                )
                quote_swapped = calculate_quote_asset_amount_swapped(
                    abs(bid_amm.quote_asset_reserve - after_swap_quote_reserves),
                    bid_amm.peg_multiplier,
                    SwapDirection.Add(),
                )

            price = (quote_swapped * BASE_PRECISION) // base_swapped
            bid_amm.base_asset_reserve = after_swap_base_reserves
            bid_amm.quote_asset_reserve = after_swap_quote_reserves

            yield L2Level(
                price=price, size=base_swapped, sources={"vamm": base_swapped}
            )
            num_bids += 1

    num_asks = 0
    top_of_book_ask_size = 0
    ask_size = abs(open_asks) // num_base_orders

    ask_amm = copy.deepcopy(updated_amm)
    ask_amm.base_asset_reserve = ask_reserves[0]
    ask_amm.quote_asset_reserve = ask_reserves[1]

    def get_l2_asks():
        nonlocal num_asks, top_of_book_ask_size, ask_size, ask_amm
        while num_asks < num_orders and ask_size > 0:
            quote_swapped = 0
            base_swapped = 0

            if top_of_book_quote_amounts and num_asks < len(top_of_book_quote_amounts):
                remaining_base_liquidity = abs(open_asks) - top_of_book_ask_size
                quote_swapped = top_of_book_quote_amounts[num_asks]
                (
                    after_swap_quote_reserves,
                    after_swap_base_reserves,
                ) = calculate_amm_reserves_after_swap(
                    ask_amm, AssetType.QUOTE(), quote_swapped, SwapDirection.Add()
                )
                base_swapped = abs(
                    ask_amm.base_asset_reserve - after_swap_base_reserves
                )

                if remaining_base_liquidity < base_swapped:
                    base_swapped = remaining_base_liquidity
                    (
                        after_swap_quote_reserves,
                        after_swap_base_reserves,
                    ) = calculate_amm_reserves_after_swap(
                        ask_amm, AssetType.BASE(), base_swapped, SwapDirection.Remove()
                    )
                    quote_swapped = calculate_quote_asset_amount_swapped(
                        abs(ask_amm.quote_asset_reserve - after_swap_quote_reserves),
                        ask_amm.peg_multiplier,
                        SwapDirection.Remove(),
                    )

                top_of_book_ask_size += base_swapped
                ask_size = (abs(open_asks) - top_of_book_ask_size) // num_base_orders

            else:
                base_swapped = ask_size
                (
                    after_swap_quote_reserves,
                    after_swap_base_reserves,
                ) = calculate_amm_reserves_after_swap(
                    ask_amm, AssetType.BASE(), base_swapped, SwapDirection.Remove()
                )
                quote_swapped = calculate_quote_asset_amount_swapped(
                    abs(ask_amm.quote_asset_reserve - after_swap_quote_reserves),
                    ask_amm.peg_multiplier,
                    SwapDirection.Remove(),
                )

            price = (quote_swapped * BASE_PRECISION) // base_swapped
            ask_amm.base_asset_reserve = after_swap_base_reserves
            ask_amm.quote_asset_reserve = after_swap_quote_reserves

            yield L2Level(
                price=price, size=base_swapped, sources={"vamm": base_swapped}
            )
            num_asks += 1

    return get_l2_bids, get_l2_asks


def group_l2_levels(
    levels: List[L2Level], grouping: int, direction: PositionDirection, depth: int
) -> List[L2Level]:
    grouped_levels = []
    for level in levels:
        price = standardize_price(level.price, grouping, direction)
        size = level.size

        if grouped_levels and grouped_levels[-1].price == price:
            current_level = grouped_levels[-1]
            current_level.size += size

            for source, additional_size in level.sources.items():
                current_level.sources[source] = (
                    current_level.sources.get(source, 0) + additional_size
                )
        else:
            grouped_level = L2Level(price=price, size=size, sources=level.soures.copy())
            grouped_levels.append(grouped_level)

        if len(grouped_levels) == depth:
            break

    return grouped_levels


def group_l2(l2: L2OrderBook, grouping: int, depth: int) -> L2OrderBook:
    return L2OrderBook(
        bids=group_l2_levels(l2.bids, grouping, PositionDirection.Long, depth),
        asks=group_l2_levels(l2.asks, grouping, PositionDirection.Short, depth),
        slot=l2.slot,
    )
