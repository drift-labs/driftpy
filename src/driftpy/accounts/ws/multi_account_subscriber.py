import asyncio
from typing import Any, Callable, Dict, Optional, cast

import websockets
import websockets.exceptions  # force eager imports
from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment
from solana.rpc.websocket_api import SolanaWsClientProtocol, connect
from solders.pubkey import Pubkey

from driftpy.accounts import DataAndSlot, get_account_data_and_slot
from driftpy.types import get_ws_url


class WebsocketMultiAccountSubscriber:
    def __init__(
        self,
        program: Program,
        commitment: Commitment = Commitment("confirmed"),
    ):
        self.program = program
        self.commitment = commitment
        self.ws: Optional[SolanaWsClientProtocol] = None
        self.task: Optional[asyncio.Task] = None

        self.subscription_map: Dict[int, Pubkey] = {}
        self.pubkey_to_subscription: Dict[Pubkey, int] = {}
        self.decode_map: Dict[Pubkey, Callable[[bytes], Any]] = {}
        self.data_map: Dict[Pubkey, Optional[DataAndSlot]] = {}
        self.initial_data_map: Dict[Pubkey, Optional[DataAndSlot]] = {}
        self.pending_subscriptions: list[Pubkey] = []

        self._lock = asyncio.Lock()

    async def add_account(
        self,
        pubkey: Pubkey,
        decode: Optional[Callable[[bytes], Any]] = None,
        initial_data: Optional[DataAndSlot] = None,
    ):
        decode_fn = decode if decode is not None else self.program.coder.accounts.decode

        async with self._lock:
            if pubkey in self.pubkey_to_subscription:
                return
            if pubkey in self.data_map and initial_data is None:
                initial_data = self.data_map[pubkey]

        if initial_data is None:
            try:
                initial_data = await get_account_data_and_slot(
                    pubkey, self.program, self.commitment, decode_fn
                )
            except Exception as e:
                print(f"Error fetching initial data for {pubkey}: {e}")
                return

        async with self._lock:
            if pubkey in self.pubkey_to_subscription:
                return

            self.decode_map[pubkey] = decode_fn
            self.initial_data_map[pubkey] = initial_data
            self.data_map[pubkey] = initial_data

        if self.ws is not None:
            try:
                # Enqueue before sending to maintain order
                async with self._lock:
                    self.pending_subscriptions.append(pubkey)

                await self.ws.account_subscribe(
                    pubkey,
                    commitment=self.commitment,
                    encoding="base64",
                )
            except Exception as e:
                print(f"Error subscribing to account {pubkey}: {e}")
                async with self._lock:
                    if (
                        self.pending_subscriptions
                        and self.pending_subscriptions[-1] == pubkey
                    ):
                        self.pending_subscriptions.pop()
                    elif pubkey in self.pending_subscriptions:
                        self.pending_subscriptions.remove(pubkey)

    async def remove_account(self, pubkey: Pubkey):
        async with self._lock:
            if pubkey not in self.pubkey_to_subscription:
                return

            subscription_id = self.pubkey_to_subscription[pubkey]

            if self.ws is not None:
                try:
                    await self.ws.account_unsubscribe(subscription_id)
                except Exception:
                    pass

            del self.subscription_map[subscription_id]
            del self.pubkey_to_subscription[pubkey]
            del self.decode_map[pubkey]
            del self.data_map[pubkey]
            if pubkey in self.initial_data_map:
                del self.initial_data_map[pubkey]

    async def subscribe(self):
        if self.task is not None:
            return

        self.task = asyncio.create_task(self._subscribe_ws())

    async def _subscribe_ws(self):
        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = get_ws_url(endpoint)

        async for ws in connect(ws_endpoint):
            try:
                self.ws = cast(SolanaWsClientProtocol, ws)

                async with self._lock:
                    initial_accounts = []
                    for pubkey in list(self.data_map.keys()):
                        if pubkey not in self.pubkey_to_subscription:
                            initial_accounts.append(pubkey)

                    self.pending_subscriptions.extend(initial_accounts)

                for pubkey in initial_accounts:
                    try:
                        await ws.account_subscribe(
                            pubkey,
                            commitment=self.commitment,
                            encoding="base64",
                        )
                    except Exception as e:
                        print(f"Error subscribing to account {pubkey}: {e}")
                        async with self._lock:
                            if pubkey in self.pending_subscriptions:
                                self.pending_subscriptions.remove(pubkey)

                async for msg in ws:
                    try:
                        if len(msg) == 0:
                            print("No message received")
                            continue

                        result = msg[0].result

                        if isinstance(result, int):
                            async with self._lock:
                                if self.pending_subscriptions:
                                    pubkey = self.pending_subscriptions.pop(0)
                                    subscription_id = result
                                    self.subscription_map[subscription_id] = pubkey
                                    self.pubkey_to_subscription[pubkey] = (
                                        subscription_id
                                    )
                                else:
                                    print(
                                        "No pending subscriptions but got a confirmation. "
                                        "This implies a race condition or mismatch."
                                    )
                            continue

                        if hasattr(result, "value") and result.value is not None:
                            subscription_id = None
                            if hasattr(msg[0], "subscription"):
                                subscription_id = msg[0].subscription

                            if (
                                subscription_id is None
                                or subscription_id not in self.subscription_map
                            ):
                                print(
                                    f"Subscription ID {subscription_id} not found in subscription map"
                                )
                                continue

                            pubkey = self.subscription_map[subscription_id]
                            decode_fn = self.decode_map.get(pubkey)

                            if decode_fn is None:
                                print(f"No decode function found for pubkey {pubkey}")
                                continue

                            try:
                                slot = int(result.context.slot)
                                account_bytes = cast(bytes, result.value.data)
                                decoded_data = decode_fn(account_bytes)
                                new_data = DataAndSlot(slot, decoded_data)
                                self._update_data(pubkey, new_data)
                            except Exception:
                                # this is RPC noise?
                                continue
                    except Exception as e:
                        print(f"Error processing websocket message: {e}")
                        continue

            except websockets.exceptions.ConnectionClosed:
                self.ws = None
                async with self._lock:
                    self.subscription_map.clear()
                    self.pubkey_to_subscription.clear()
                continue
            except Exception as e:
                print(f"Error in websocket connection: {e}")
                self.ws = None
                async with self._lock:
                    self.subscription_map.clear()
                    self.pubkey_to_subscription.clear()
                await asyncio.sleep(1)
                continue

    def _update_data(self, pubkey: Pubkey, new_data: Optional[DataAndSlot]):
        if new_data is None:
            return

        current_data = self.data_map.get(pubkey)
        if current_data is None or new_data.slot >= current_data.slot:
            self.data_map[pubkey] = new_data

    def get_data(self, pubkey: Pubkey) -> Optional[DataAndSlot]:
        return self.data_map.get(pubkey)

    async def fetch(self, pubkey: Optional[Pubkey] = None):
        if pubkey is not None:
            decode_fn = self.decode_map.get(pubkey)
            if decode_fn is None:
                return
            new_data = await get_account_data_and_slot(
                pubkey, self.program, self.commitment, decode_fn
            )
            self._update_data(pubkey, new_data)
        else:
            tasks = []
            for pubkey, decode_fn in self.decode_map.items():
                tasks.append(
                    get_account_data_and_slot(
                        pubkey, self.program, self.commitment, decode_fn
                    )
                )
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for pubkey, result in zip(self.decode_map.keys(), results):
                if isinstance(result, Exception):
                    continue
                self._update_data(pubkey, result)

    def is_subscribed(self):
        return self.ws is not None and self.task is not None

    async def unsubscribe(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        if self.ws:
            async with self._lock:
                for subscription_id in list(self.subscription_map.keys()):
                    try:
                        await self.ws.account_unsubscribe(subscription_id)
                    except Exception:
                        pass
            await self.ws.close()
            self.ws = None

        async with self._lock:
            self.subscription_map.clear()
            self.pubkey_to_subscription.clear()
            self.decode_map.clear()
            self.data_map.clear()
            self.initial_data_map.clear()
            self.pending_subscriptions.clear()
