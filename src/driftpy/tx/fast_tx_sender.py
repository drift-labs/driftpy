import asyncio

from typing import Optional, Sequence

from solders.hash import Hash
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.instruction import Instruction
from solders.message import MessageV0

from solana.transaction import Transaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Commitment, Confirmed

from driftpy.tx.types import TxSender, TxSigAndSlot


class FastTxSender(TxSender):
    def __init__(
        self,
        connection: AsyncClient,
        opts: TxOpts,
        additional_connections: Optional[list[AsyncClient]] = None,
        blockhash_commitment: Commitment = Confirmed,
    ):
        self.connection = connection
        self.opts = opts
        self.blockhash_commitment = blockhash_commitment
        self.additional_connections = additional_connections

    async def start_blockhash_refresh_loop(self):
        """
        Must be called with asyncio.create_task to prevent blocking
        """
        while True:
            try:
                blockhash_info = await self.connection.get_latest_blockhash(
                    self.blockhashCommitment
                )
                self.recentBlockhash = blockhash_info.blockhash
            except Exception as e:
                print(f"Error in start_blockhash_refresh_loop: {e}")
            await asyncio.sleep(
                self.blockhashRefreshInterval / 1000
            )  # Convert milliseconds to seconds

    async def get_blockhash(self) -> Hash:
        return (
            await self.connection.get_latest_blockhash(self.blockhash_commitment)
        ).value.blockhash

    async def get_legacy_tx(
        self,
        ixs: Sequence[Instruction],
        payer: Keypair,
        additional_signers: Optional[Sequence[Keypair]],
    ) -> Transaction:
        latest_blockhash = await self.get_blockhash()
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
        latest_blockhash = await self.get_blockhash()
        msg = MessageV0.try_compile(
            payer.pubkey(), ixs, lookup_tables, latest_blockhash
        )

        signers = [payer]
        if additional_signers is not None:
            [signers.append(signer) for signer in additional_signers]

        return VersionedTransaction(msg, signers)
