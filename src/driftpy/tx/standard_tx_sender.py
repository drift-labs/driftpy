from solders.hash import Hash
from solders.signature import Signature

from driftpy.tx.types import TxSender, TxSigAndSlot
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from typing import Union

from solders.rpc.responses import SendTransactionResp
from solana.transaction import Transaction
from solders.transaction import VersionedTransaction


class StandardTxSender(TxSender):
    def __init__(self, connection: AsyncClient, opts: TxOpts):
        self.connection = connection
        if opts.skip_confirmation:
            raise ValueError("RetryTxSender doesnt support skip confirmation")

        self.opts = opts

    async def get_blockhash(self) -> Hash:
        return (
            await self.connection.get_latest_blockhash(self.opts.preflight_commitment)
        ).value.blockhash

    async def send(self, tx: Union[Transaction, VersionedTransaction]) -> TxSigAndSlot:
        raw = tx.serialize() if isinstance(tx, Transaction) else bytes(tx)

        body = self.connection._send_raw_transaction_body(raw, self.opts)
        resp = await self.connection._provider.make_request(body, SendTransactionResp)
        sig = resp.value

        sig_status = await self.connection.confirm_transaction(
            sig, self.opts.preflight_commitment
        )
        slot = sig_status.context.slot

        return TxSigAndSlot(sig, slot)
