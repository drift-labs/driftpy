raise ImportError(
    "The jito_subscriber module is deprecated and has been removed in driftpy."
)

import asyncio
import random
from typing import Optional, Tuple, Union

from jito_searcher_client.async_searcher import (
    get_async_searcher_client,  # type: ignore
)
from jito_searcher_client.generated.searcher_pb2 import (
    ConnectedLeadersRequest,
    ConnectedLeadersResponse,
    GetTipAccountsRequest,
    GetTipAccountsResponse,
    SubscribeBundleResultsRequest,
)  # type: ignore
from jito_searcher_client.generated.searcher_pb2_grpc import (
    SearcherServiceStub,  # type: ignore
)
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import TransferParams, transfer


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
        tip_accounts: GetTipAccountsResponse = (
            await self.searcher_client.GetTipAccounts(GetTipAccountsRequest())
        )  # type: ignore
        for account in tip_accounts.accounts:
            self.tip_accounts.append(Pubkey.from_string(account))
        while True:
            try:
                self.cache.clear()
                current_slot = (await self.connection.get_slot(Confirmed)).value
                leaders: ConnectedLeadersResponse = (
                    await self.searcher_client.GetConnectedLeaders(
                        ConnectedLeadersRequest()
                    )
                )  # type: ignore
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

    def send_to_jito(self, current_slot: int) -> bool:
        for slot in range(current_slot - 5, current_slot + 5):
            if slot in self.cache:
                return True
        return False

    def get_tip_ix(self, signer: Pubkey, tip_amount: int = 1_000_000):
        tip_account = random.choice(self.tip_accounts)
        transfer_params = TransferParams(
            from_pubkey=signer, to_pubkey=tip_account, lamports=tip_amount
        )
        return transfer(transfer_params)

    async def process_bundle_result(self, uuid: str) -> Tuple[bool, Union[int, str]]:
        while True:
            bundle_result = await self.bundle_subscription.read()  # type: ignore
            if bundle_result.bundle_id == uuid:
                if bundle_result.HasField("accepted"):
                    slot = getattr(getattr(bundle_result, "accepted"), "slot")
                    return True, slot or 0
                elif bundle_result.HasField("rejected"):
                    msg = getattr(
                        getattr(
                            getattr(bundle_result, "rejected"), "simulation_failure"
                        ),
                        "msg",
                    )
                    return False, msg or ""
