import asyncio
import random

from typing import Optional

from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from spl.token.instructions import (
    transfer as transfer_ix,
    TransferParams,
    TOKEN_PROGRAM_ID,
)

from jito_searcher_client.async_searcher import get_async_searcher_client  # type: ignore
from jito_searcher_client.generated.searcher_pb2_grpc import SearcherServiceStub  # type: ignore
from jito_searcher_client.generated.searcher_pb2 import ConnectedLeadersResponse, ConnectedLeadersRequest, GetTipAccountsRequest, GetTipAccountsResponse, SubscribeBundleResultsRequest  # type: ignore


class JitoSubscriber:
    def __init__(
        self,
        refresh_rate: int,
        kp: Keypair,
        connection: AsyncClient,
        block_engine_url: str,
    ):
        self.cache = []  # type: ignore
        self.refresh_rate = refresh_rate
        self.kp = kp
        self.searcher_client: Optional[SearcherServiceStub] = None
        self.connection = connection
        self.tip_accounts: list[Pubkey] = []
        self.block_engine_url = block_engine_url
        self.bundle_subscription = None

    async def subscribe(self):
        self.searcher_client = await get_async_searcher_client(
            self.block_engine_url, self.kp
        )
        asyncio.create_task(self._subscribe())

    async def _subscribe(self):
        self.bundle_subscription = self.searcher_client.SubscribeBundleResults(
            SubscribeBundleResultsRequest()
        )
        tip_accounts: GetTipAccountsResponse = await self.searcher_client.GetTipAccounts(GetTipAccountsRequest())  # type: ignore
        for account in tip_accounts.accounts:
            self.tip_accounts.append(Pubkey.from_string(account))
        while True:
            try:
                self.cache.clear()
                current_slot = (await self.connection.get_slot(Confirmed)).value
                leaders: ConnectedLeadersResponse = await self.searcher_client.GetConnectedLeaders(ConnectedLeadersRequest())  # type: ignore
                for slot_list in leaders.connected_validators.values():
                    slots = slot_list.slots
                    for slot in slots:
                        if slot > current_slot:
                            self.cache.append(slot)
                self.cache.sort()

            except Exception as e:
                print(e)
                await asyncio.sleep(30)
                await self._subscribe()
            await asyncio.sleep(self.refresh_rate)

    # def send_to_jito(self, current_slot: int) -> bool:
    #     print("checking?")
    #     for slot in range(current_slot - 5, current_slot + 5):
    #         print(slot)
    #         if slot in self.cache:
    #             print('sending to jito')
    #             return True
    #     return False

    def send_to_jito(self, current_slot: int) -> tuple[bool, int]:
        closest_slot = None
        min_distance = float("inf")
        jito = False

        print(len(self.cache))
        print(self.cache[-1])
        print(current_slot > self.cache[-1])
        # Iterate through the cache to find the closest future slot
        for slot in self.cache:
            # Only consider slots greater than the current slot
            if slot > current_slot:
                distance = slot - current_slot
                if distance < min_distance:
                    min_distance = distance
                    closest_slot = slot

        print("Closest future slot:", closest_slot, "Current slot:", current_slot)

        # Check if a closest future slot exists and is within 5 slots from the current
        if closest_slot is not None and min_distance <= 5:
            jito = True

        # If no closest future slot is found, the function behaves as if it's sending to JITO with the current slot.
        # If closest_slot remains None, it means no future slots were found.
        # Depending on your use case, you might need to adjust this behavior.
        return jito, closest_slot if closest_slot is not None else 0

    def get_tip_ix(self, signer: Pubkey, tip_amount: int = 1_000_000):
        tip_account = random.choice(self.tip_accounts)
        transfer_params = TransferParams(
            TOKEN_PROGRAM_ID, signer, tip_account, signer, tip_amount, [signer]
        )
        return transfer_ix(transfer_params)

    async def process_bundle_result(self, uuid: str) -> bool:
        while True:
            bundle_result = await self.bundle_subscription.read()  # type: ignore
            print(bundle_result)
            if bundle_result.bundle_id == uuid:
                if bundle_result.HasField("accepted"):
                    return True
                elif bundle_result.HasField("rejected"):
                    return False
