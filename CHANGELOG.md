# Changelog

## [0.7.6] - 2023-12-21

Added `DLOB`, `DLOBClient`, and corresponding math

Added `AuctionSubscriber` class

Added `SlotSubscriber` class

Stabilized `UserMap` WebSocket Subscription

Fixed issue where `get_non_idle_user_filter` would return an empty filter

## [0.7.8] - 2024-1-8

Fixed several math errors in `amm.py`, `repeg.py`, `oracles.py`

Fixed bug where `DriftUser.get_free_collateral()` would always return 0

Added equivalent math in `funding.py` to match TypeScript SDK

Removed `sub_account_id` field from `DriftUser`

Changed `UserMap` to assign slots from the `getProgramAccounts` RPC call

Updated `constants/perp_markets.py` with new perp market listings

## [0.7.9] - 2024-1-8

Fix breaking bug in `DriftClient.get_jupiter_swap_ix_v6` where token accounts wouldn't be created properly

## [0.7.10] - 2024-1-11

Add `get_l2_orderbook_sync` and `get_l3_orderbook_sync` to `DLOBClient` for building orderbooks from `DLOB` instead of `DLOB-server`

Refactor the `WebsocketDriftClientAccountSubscriber` subscription logic to reduce 429s

## [0.7.11] - 2024-1-12

Update `drift.json` IDL for Drift Program

## [0.7.12] - 2024-1-15

Fix several major math bugs in `DriftUser.get_perp_liq_price()` and downstream math functions

Add default `Confirmed` commitment in `StandardTxSender`

## [0.7.14] - 2024-1-18

Add `PriorityFeeSubscriber`

## [0.7.15] - 2024-1-18

Fix bug where `PriorityFeeSubscriber.subscribe()` blocks

## [0.7.17] - 2024-1-19

Refactor math entirely to align more closely with TypeScript SDK

Add some math functions to `orders.py`, `amm.py`, and `oracles.py`

Update casing conventions for `ExchangeStatus`

Add `find_nodes_to_trigger()`  to `dlob.py`

Add `get_slot()` to `user_map.py`

## [0.7.18] - 2024-1-25

Minor tweaks to `UserMap`

## [0.7.19] - 2024-1-29

Add `FastTxSender`

## [0.7.20] - 2024-1-30

Add `determine_maker_and_taker` and `find_crossing_resting_limit_orders` to `DLOB`

Fix bugs with lambda functions in `DLOB`

Add `get_settle_perp_ixs`, `get_fill_perp_order_ix` `get_revert_fill_ix`,  `get_trigger_order_ix`, `force_cancel_orders`, and `get_force_cancel_orders_ix` to `DriftClient`

Fix bugs in `amm.py`

Fix bugs in `exchange_status.py`

Update funding calculations in `funding.py/calculate_all_estimated_funding_rate`

Increase RPC timeout in `PriorityFeeSubscriber.load()` from 5 to 20 seconds

Increase RPC timeout in `UserMap.sync()` from 10 to 30 seconds

Fix bug with python versions > 3.10 with mutable default struct fields in `types.py/OrderParams`

Several semantics changes throughout the codebase

## [0.7.21] - 2024-2-1

Fix blocking bug in `FastTxSender`

## [0.7.23] - 2024-2-8

Add `derive_oracle_auction_params()`

Add `time_remaining_until_update()`

Add `calculate_borrow_rate()`

Add `calculate_interest_rate()`

Add `calculate_utilization()`

Add `calculate_spot_market_borrow_capacity()`

Add `calculate_reference_price_offset()`

Add `calculate_inventory_liquidity_ratio()`

Add `get_new_oracle_conf_pct()`

Add `DriftUser.is_being_liquidated()`

Fix several bugs in several math functions

Fix bug in `DriftClient.get_jupiter_swap_ix_v6()`

Add math unit tests for `derive_oracle_auction_params()`, `calculate_long_short_funding_and_live_twaps()`, `time_remaining_until_update()`, `calculate_size_premium_liability_weight()`, `calculate_borrow_rate()`, `calculate_deposit_rate()`, `calculate_spot_market_borrow_capacity`, `calculate_inventory_scale()`, `calculate_spread_bn()`, `calculate_price()`, `calculate_spread_reserves()`, `calculate_reference_price_offset()`, `calculate_inventory_liquidity_ratio()`, `calculate_live_oracle_twap()`, `calculate_live_oracle_std()`, `get_new_oracle_conf_pct()`, `is_oracle_valid()`, `calculate_position_pnl()`, `get_worst_case_token_amounts()`, `DriftUser.get_free_collateral()`, `DriftUser.get_health()`, `DriftUser.get_max_leverage_for_perps()`, `DriftUser.get_active_perp_positions()`, `DriftUser.get_unrealized_pnl()`, `DriftUser.can_be_liquidated()`, `DriftUser.get_token_amount()`, `DriftUser.get_net_spot_market_value()`, `DriftUser.get_spot_market_asset_and_liability_value()`

Add `OraclePriceData.default()`

Add default values for padding in structs

Bump `requests` and `typing-extensions` to ^ instead of pinned

## [0.7.24] - 2024-2-10

Update `drift.json` IDL

## [0.7.25] - 2024-2-20

Fix bug in `decode_user()` where `remainder_base_amount` would decode incorrectly

## [0.7.26] - 2024-2-26

Filter out logs with errors in `websocket_log_provider.py` to avoid `EventSubscriber` returning false positive events

## [0.7.27] - 2024-2-27

Fix bug where `MarketMap.unsubscribe()` wasn't properly awaited

## [0.7.29] - 2024-2-28

Fix bug where `DriftClient.unsubscribe()` wasn't properly awaited

## [0.7.30] - 2024-2-28

Add support for hot-swapping oracles without SDK dying

Add custom event parsing in events/parse.py

## [0.7.31] - 2024-2-28

Fix bug where `DriftClient.unsubscribe()` scheduled tasks on an already-running event loop

## [0.7.32] - 2024-2-29

Add guardrails to avoid `CachedDriftClientAccountSubscriber` panicking on cache fetch `IndexError`s

Add `perp_market_indexes`, `spot_market_indexes`, `oracle_infos`, `should_find_all_markets_and_oracles` to `CachedDriftClientAccountSubscriber`

Add `stack_trace()` utility function