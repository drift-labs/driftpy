raise ImportError(
    "The jito_tx_sender module is deprecated and has been removed in driftpy. "
)

import asyncio
from typing import Optional, Union

from jito_searcher_client.convert import (
    tx_to_protobuf_packet,
    versioned_tx_to_protobuf_packet,
)
from jito_searcher_client.generated.bundle_pb2 import Bundle
from jito_searcher_client.generated.searcher_pb2 import (
    SendBundleRequest,
    SendBundleResponse,
)
from solana.rpc.commitment import Commitment, Confirmed
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
from solders.keypair import Keypair  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from driftpy.drift_client import DriftClient
from driftpy.slot.slot_subscriber import SlotSubscriber
from driftpy.tx.fast_tx_sender import FastTxSender
from driftpy.tx.jito_subscriber import JitoSubscriber
from driftpy.tx.types import TxSigAndSlot


class JitoTxSender(FastTxSender):
    def __init__(
        self,
        drift_client: DriftClient,
        opts: TxOpts,
        block_engine_url: str,
        jito_keypair: Keypair,
        blockhash_commitment: Commitment = Confirmed,
        blockhash_refresh_interval_secs: Optional[int] = None,
        tip_amount: Optional[int] = None,
    ):
        super().__init__(
            drift_client.connection,
            opts,
            blockhash_refresh_interval_secs or 5,
            blockhash_commitment,
        )
        self.block_engine_url = block_engine_url
        self.jito_keypair = jito_keypair
        self.jito_subscriber = JitoSubscriber(
            30, jito_keypair, drift_client.connection, block_engine_url
        )
        self.slot_subscriber = SlotSubscriber(drift_client)
        self.payer = drift_client.wallet.payer
        self.tip_amount = tip_amount or 1_000_000
        asyncio.create_task(self.jito_subscriber.subscribe())
        asyncio.create_task(self.slot_subscriber.subscribe())
        asyncio.create_task(super().subscribe_blockhash())

    async def send(self, tx: Union[Transaction, VersionedTransaction]) -> TxSigAndSlot:
        slot = self.slot_subscriber.get_slot()
        if self.jito_subscriber.send_to_jito(slot):
            searcher_client = self.jito_subscriber.searcher_client
            tip_packet = versioned_tx_to_protobuf_packet(
                await super().get_versioned_tx(
                    [self.jito_subscriber.get_tip_ix(self.payer.pubkey())],
                    self.payer,
                    [],
                    [],
                )
            )
            if isinstance(tx, Transaction):
                tx_packet = tx_to_protobuf_packet(tx)
            else:
                tx_packet = versioned_tx_to_protobuf_packet(tx)
            bundle = Bundle(packets=[tx_packet, tip_packet])
            try:
                result: SendBundleResponse = await searcher_client.SendBundle(
                    SendBundleRequest(bundle=bundle)
                )
                uuid = result.uuid
                bundle_result = await self.jito_subscriber.process_bundle_result(uuid)
                match bundle_result[0]:
                    case True:
                        return TxSigAndSlot(tx.signatures[0], bundle_result[1])
                    case False:
                        raise ValueError(
                            f"Bundle was not processed: {bundle_result[1]}"
                        )
            except Exception as e:
                raise ValueError(f"Error sending bundle: {e}")
        else:
            return await super().send(tx)
