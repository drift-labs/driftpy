from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.signature import Signature
from solders.transaction import VersionedTransaction


@dataclass
class TxSigAndSlot:
    tx_sig: Signature
    slot: int


class TxSender:
    @abstractmethod
    async def get_versioned_tx(
        self,
        ixs: Sequence[Instruction],
        payer: Keypair,
        lookup_tables: Sequence[AddressLookupTableAccount],
        additional_signers: Optional[Sequence[Keypair]],
    ) -> VersionedTransaction:
        pass

    @abstractmethod
    async def send(self, tx: VersionedTransaction) -> TxSigAndSlot:
        pass
