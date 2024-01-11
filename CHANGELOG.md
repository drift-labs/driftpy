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