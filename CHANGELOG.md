# Changelog

## [0.7.6] - 2023-12-21

Added `DLOB`, `DLOBClient`, and corresponding math

Added `AuctionSubscriber` class

Added `SlotSubscriber` class

Stabilized `UserMap` WebSocket Subscription

Fixed issue where `get_non_idle_user_filter` would return an empty filter

## [0.7.8] - 2024-1-8

Fixed several math errors in `amm.py`, `repeg.py`, `oracles.py`

Added equivalent math in `funding.py` to match TypeScript SDK

Removed `sub_account_id` field from `DriftUser`

Changed `UserMap` to assign slots from the `getProgramAccounts` RPC call