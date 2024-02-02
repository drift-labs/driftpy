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


