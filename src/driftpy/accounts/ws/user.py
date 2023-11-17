import asyncio
from typing import Optional

from anchorpy import Program
from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

from driftpy.accounts import get_user_account_and_slot
from driftpy.accounts import UserAccountSubscriber, DataAndSlot
from driftpy.types import User

import websockets
import websockets.exceptions  # force eager imports
from solana.rpc.websocket_api import connect

from typing import cast


class WebsocketUserAccountSubscriber(UserAccountSubscriber):
    def __init__(
        self,
        user_pubkey: Pubkey,
        program: Program,
        commitment: Commitment = "confirmed",
    ):
        self.program = program
        self.commitment = commitment
        self.user_pubkey = user_pubkey
        self.user_and_slot = None

        self.task = None
        self.ws = None
        self.subscription_id = None

    async def subscribe(self):
        await self._subscribe()

    async def _subscribe(self):
        print('here9')
        ws_endpoint = self.program.provider.connection._provider.endpoint_uri.replace("https", "wss")
        async for ws in connect(ws_endpoint):
            try:
                await ws.account_subscribe(# type: ignore
                    self.user_pubkey,
                    commitment=self.commitment,
                    encoding="base64",
                )
                first_resp = await ws.recv()
                subscription_id = cast(int, first_resp[0].result)  # type: ignore
                print(f"Subscription id: {subscription_id}")
                async for msg in ws:
                    try:
                        slot = int(msg[0].result.context.slot)  # type: ignore
                        account_bytes = cast(bytes, msg[0].result.value.data)  # type: ignore
                        decoded_data = self.program.coder.accounts.decode(account_bytes)
                        self.user_and_slot = DataAndSlot(slot, decoded_data)
                        print("here")
                    except Exception:
                        print(f"Error processing account data")
                        break
                await ws.account_unsubscribe(subscription_id)  # type: ignore
            except websockets.exceptions.ConnectionClosed:
                print("Websocket closed, reconnecting...")
                continue

    async def get_user_account_and_slot(self) -> Optional[DataAndSlot[User]]:
        return self.user_and_slot

    async def unsubscribe(self):
        self.task.cancel()
        self.task = None
