from abc import abstractmethod
from dataclasses import dataclass
from typing import Union, Sequence

from solders.hash import Hash
from solders.signature import Signature
from solana.transaction import Transaction
from solders.transaction import VersionedTransaction


@dataclass
class TxSigAndSlot:
    tx_sig: Signature
    slot: int


class TxSender:
    @abstractmethod
    async def get_blockhash(self) -> Hash:
        pass

    @abstractmethod
    async def send(self, tx: Union[Transaction, VersionedTransaction]) -> TxSigAndSlot:
        pass
