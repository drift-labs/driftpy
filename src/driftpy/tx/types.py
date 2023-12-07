from abc import abstractmethod
from dataclasses import dataclass
from typing import Union, Sequence, Optional

from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.keypair import Keypair
from solders.signature import Signature
from solders.instruction import Instruction
from solana.transaction import Transaction
from solders.transaction import VersionedTransaction


@dataclass
class TxSigAndSlot:
    tx_sig: Signature
    slot: int


class TxSender:
    @abstractmethod
    async def get_legacy_tx(
        self,
        ixs: Sequence[Instruction],
        payer: Keypair,
        additional_signers: Optional[Sequence[Keypair]],
    ) -> Transaction:
        pass

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
    async def send(self, tx: Union[Transaction, VersionedTransaction]) -> TxSigAndSlot:
        pass
