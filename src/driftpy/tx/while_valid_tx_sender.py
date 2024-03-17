import asyncio

from typing import Union, Optional, Sequence

from anchorpy import Wallet

from solders.transaction import VersionedTransaction  # type: ignore
from solders.rpc.responses import SendTransactionResp, RpcBlockhash  # type: ignore
from solders.hash import Hash  # type: ignore
from solders.keypair import Keypair  # type: ignore
from solders.instruction import Instruction  # type: ignore
from solders.address_lookup_table_account import AddressLookupTableAccount  # type: ignore
from solders.message import MessageV0  # type: ignore

from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Commitment, Confirmed
from solana.transaction import Transaction


from driftpy.tx.types import TxSigAndSlot, TxSender
from driftpy.slot.slot_subscriber import SlotSubscriber
from driftpy.drift_client import DriftClient

DEFAULT_RETRY_SLEEP = 8


class WhileValidTxSender(TxSender):
    def __init__(
        self,
        connection: AsyncClient,
        opts: TxOpts,
        blockhash_commitment: Commitment = Confirmed,
        retry_interval: int = DEFAULT_RETRY_SLEEP,
    ):
        self.connection = connection
        self.opts = opts
        self.blockhash_commitment = blockhash_commitment
        self.retry_interval = retry_interval
        self.blockhash_to_blockheight: dict[str, int] = {}
        self.slot_subscriber = SlotSubscriber(DriftClient(connection, Wallet.dummy()))
        asyncio.create_task(self.slot_subscriber.subscribe())

    async def get_blockhash_and_blockheight(self) -> RpcBlockhash:
        return (
            await self.connection.get_latest_blockhash(self.blockhash_commitment)
        ).value

    async def fetch_latest_blockhash_and_blockheight(self) -> RpcBlockhash:
        return await self.get_blockhash_and_blockheight()

    async def get_legacy_tx(
        self,
        ixs: Sequence[Instruction],
        payer: Keypair,
        additional_signers: Optional[Sequence[Keypair]],
    ) -> Transaction:
        rpc_blockhash = await self.fetch_latest_blockhash_and_blockheight()
        latest_blockhash = rpc_blockhash.blockhash
        last_valid_blockheight = rpc_blockhash.last_valid_block_height
        self.blockhash_to_blockheight[str(latest_blockhash)] = last_valid_blockheight

        tx = Transaction(
            instructions=ixs,
            recent_blockhash=latest_blockhash,
            fee_payer=payer.pubkey(),
        )

        tx.sign_partial(payer)

        if additional_signers is not None:
            [tx.sign_partial(signer) for signer in additional_signers]

        return tx

    async def get_versioned_tx(
        self,
        ixs: Sequence[Instruction],
        payer: Keypair,
        lookup_tables: Sequence[AddressLookupTableAccount],
        additional_signers: Optional[Sequence[Keypair]],
    ) -> VersionedTransaction:
        rpc_blockhash = await self.fetch_latest_blockhash_and_blockheight()
        latest_blockhash = rpc_blockhash.blockhash
        last_valid_blockheight = rpc_blockhash.last_valid_block_height
        self.blockhash_to_blockheight[str(latest_blockhash)] = last_valid_blockheight

        msg = MessageV0.try_compile(
            payer.pubkey(), ixs, lookup_tables, latest_blockhash
        )

        signers = [payer]
        if additional_signers is not None:
            [signers.append(signer) for signer in additional_signers]

        return VersionedTransaction(msg, signers)

    async def send(self, tx: Union[Transaction, VersionedTransaction]) -> TxSigAndSlot:
        flag = asyncio.Event()

        if isinstance(tx, Transaction):
            last_valid_blockheight: int = self.blockhash_to_blockheight[
                str(tx.recent_blockhash)
            ]
            print(last_valid_blockheight)
        else:
            last_valid_blockheight: int = self.blockhash_to_blockheight[
                str(tx.message.recent_blockhash)
            ]
            print(last_valid_blockheight)

        async def retry_send_and_confirm():
            while not flag.is_set():
                raw = tx.serialize() if isinstance(tx, Transaction) else bytes(tx)
                body = self.connection._send_raw_transaction_body(raw, self.opts)
                resp = await self.connection._provider.make_request(
                    body, SendTransactionResp
                )
                sig = resp.value
                try:
                    sig_status = await self.connection.confirm_transaction(
                        sig, self.opts.preflight_commitment
                    )
                    print(sig_status)
                    if sig_status is not None:
                        slot = sig_status.context.slot
                        return TxSigAndSlot(sig, slot)
                except Exception as e:
                    print(e)
                await asyncio.sleep(self.retry_interval)
                counter += 1
            raise Exception("Transaction expired before confirmation")

        def on_slot_change(slot):
            if slot > last_valid_blockheight:
                flag.set()

        self.slot_subscriber.event_emitter.on_slot_change += on_slot_change

        try:
            return await retry_send_and_confirm()
        finally:
            self.slot_subscriber.event_emitter.on_slot_change -= on_slot_change
