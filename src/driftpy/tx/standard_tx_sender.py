from typing import Optional, Sequence

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed
from solana.rpc.types import TxOpts
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.hash import Hash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import MessageV0
from solders.rpc.responses import SendTransactionResp
from solders.transaction import VersionedTransaction

from driftpy.tx.types import TxSender, TxSigAndSlot


class StandardTxSender(TxSender):
    def __init__(
        self,
        connection: AsyncClient,
        opts: TxOpts,
        blockhash_commitment: Commitment = Confirmed,
    ):
        self.connection = connection
        if opts.skip_confirmation:
            raise ValueError("RetryTxSender doesnt support skip confirmation")
        self.opts = opts
        self.blockhash_commitment = blockhash_commitment

    async def get_blockhash(self) -> Hash:
        return (
            await self.connection.get_latest_blockhash(self.blockhash_commitment)
        ).value.blockhash

    async def fetch_latest_blockhash(self) -> Hash:
        return await self.get_blockhash()

    async def get_versioned_tx(
        self,
        ixs: Sequence[Instruction],
        payer: Keypair,
        lookup_tables: Sequence[AddressLookupTableAccount],
        additional_signers: Optional[Sequence[Keypair]] = None,
    ) -> VersionedTransaction:
        latest_blockhash = await self.fetch_latest_blockhash()

        msg = MessageV0.try_compile(
            payer.pubkey(), ixs, lookup_tables, latest_blockhash
        )

        signers = [payer]
        if additional_signers is not None:
            [signers.append(signer) for signer in additional_signers]

        return VersionedTransaction(msg, signers)

    async def send(self, tx: VersionedTransaction) -> TxSigAndSlot:
        raw = bytes(tx)

        body = self.connection._send_raw_transaction_body(raw, self.opts)
        resp = await self.connection._provider.make_request(body, SendTransactionResp)

        if not isinstance(resp, SendTransactionResp):
            raise Exception(f"Unexpected response from send transaction: {resp}")

        sig = resp.value

        sig_status = await self.connection.confirm_transaction(
            sig, self.opts.preflight_commitment
        )
        slot = sig_status.context.slot

        return TxSigAndSlot(sig, slot)

    async def send_no_confirm(self, tx: VersionedTransaction) -> TxSigAndSlot:
        raw = bytes(tx)

        body = self.connection._send_raw_transaction_body(raw, self.opts)
        resp = await self.connection._provider.make_request(body, SendTransactionResp)
        sig = resp.value

        return TxSigAndSlot(sig, 0)
