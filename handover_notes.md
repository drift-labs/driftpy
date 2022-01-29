# Handover Notes

Delete this file when it's no longer relevant.

## Things to do

This code covers `ClearingHouse` and the `ClearingHouse` tests that don't require `ClearingHouseUser`.
Writing those tests also required writing `admin.py`, `types.py` and some constants in `src/constants`.
So you need to write what's left.

Also, I copied docstrings from the TS client but most of the methods didn't have docstrings
and I don't really have enough context to write good docstrings for them.

## Things to note

- The development setup instructions are in the README.
- The IDLs are copied into `src/driftpy/idl`. You can load the `clearing_house` IDL from there by using `ClearingHouse.local_idl()`.
You can also just fetch the IDL on-chain of course.
- Running the tests on localnet currently requires changing the program ID in `drift-core/programs/clearing_house/src/lib.rs`.
Don't commit the lib.rs change or it will be confusing for people.

### Differences from the TypeScript client

- The methods for generating instructions (e.g. `get_deposit_collateral_ix`) are all public.
Everything is public in Python anyway but also these methods should be considered public
for the sake of people who are using them to build complex transactions, using their own RPC client etc.
- There is no subscriber interface. All the methods that require dynamic data will fetch it for you if you want, but you can also prefetch that data yourself and pass it as a argument. For example, see how `get_update_funding_rate_ix` will call `get_state_account()` if you don't pass a `state_account` argument.
- There are no wallet or provider parameters in this code. When the library user wants to customise those things they can do so when creating the `Program` object that they pass to `ClearingHouse.create`. That Program object takes a `provider` argument, and `anchorpy.Provider` takes a `Wallet` argument. This stuff is simpler in Python because we don't have to think about web browsers and stuff.
- We use `ClearingHouse.create` instead of `ClearingHouse.from` because the method works differently and some other reasons.
