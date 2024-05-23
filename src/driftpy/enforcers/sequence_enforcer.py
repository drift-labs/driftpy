from typing import cast, Optional
import anchorpy
import driftpy

from pathlib import Path
from anchorpy import Program, Idl, Provider, Wallet, Context
from solders.pubkey import Pubkey
from solders.instruction import Instruction
from solders.system_program import ID as SystemProgram

from solana.rpc.async_api import AsyncClient
from driftpy.addresses import get_sequencer_public_key_and_bump
from driftpy.constants.config import SEQUENCER_PROGRAM_ID, DEVNET_SEQUENCER_PROGRAM_ID
from driftpy.types import SequenceAccount


class SequenceEnforcer:
    def __init__(self, connection: AsyncClient, wallet: Wallet, env):
        self.sequence_number_by_subaccount = {}
        self.sequence_init_by_subaccount = {}
        self.sequence_address_by_subaccount = {}
        self.sequence_bump_by_subaccount = {}
        self.resetting_sequence = False
        self.wallet = wallet
        file = Path(str(driftpy.__path__[0]) + "/idl/sequence_enforcer.json")
        with file.open():
            raw = file.read_text()
        idl = Idl.from_json(raw)

        provider = Provider(connection, wallet)
        self.sequence_enforcer_pid = SEQUENCER_PROGRAM_ID if env == "mainnet" else DEVNET_SEQUENCER_PROGRAM_ID
        self.sequence_enforcer_program = Program(
            idl,
            self.sequence_enforcer_pid,
            provider,
        )

    async def load_sequence_info(self, subaccounts: list):
        for subaccount in subaccounts:
            address, bump = get_sequencer_public_key_and_bump(
                self.sequence_enforcer_pid, self.wallet.payer.pubkey(), subaccount
            )
            try:
                sequence_account_raw = await self.sequence_enforcer_program.account[
                    "SequenceAccount"
                ].fetch(address)
            except anchorpy.error.AccountDoesNotExistError:
                self.set_sequence_address_for_subaccount(subaccount, address)
                self.set_sequence_bump_for_subaccount(subaccount, bump)
                self.set_sequence_number_for_subaccount(subaccount, 1)
                self.set_sequence_init_for_subaccount(subaccount, False)
                continue
            sequence_account = cast(SequenceAccount, sequence_account_raw)
            self.set_sequence_address_for_subaccount(subaccount, address)
            self.set_sequence_bump_for_subaccount(subaccount, bump)
            self.set_sequence_number_for_subaccount(
                subaccount, sequence_account.sequence_num + 1
            )
            self.set_sequence_init_for_subaccount(subaccount, True)

    def get_sequence_init_ix(self, subaccount: int = 0) -> Instruction:
        return self.sequence_enforcer_program.instruction["initialize"](
            self.get_sequence_bump_for_subaccount(subaccount),
            str(subaccount),
            ctx=Context(
                accounts={
                    "sequence_account": self.get_sequence_address_for_subaccount(
                        subaccount
                    ),
                    "authority": self.wallet.payer.pubkey(),
                    "system_program": SystemProgram,
                }
            ),
        )

    def get_reset_sequence_number_ix(
        self, sequence_number: int, subaccount: int = 0
    ) -> Instruction:
        return self.sequence_enforcer_program.instruction["reset_sequence_number"](
            sequence_number,
            ctx=Context(
                accounts={
                    "sequence_account": self.get_sequence_address_for_subaccount(
                        subaccount
                    ),
                    "authority": self.wallet.payer.pubkey(),
                }
            ),
        )

    def get_check_and_set_sequence_number_ix(
        self, sequence_number: Optional[int] = None, subaccount: int = 0
    ):
        current_for_subaccount = self.get_sequence_number_for_subaccount(subaccount)
        sequence_number = sequence_number or current_for_subaccount

        if (
            sequence_number < current_for_subaccount - 1
        ):  # we increment after creating the ix, so we check - 1
            print(
                f"WARNING: sequence number {sequence_number} < last used {current_for_subaccount - 1}"
            )

        ix = self.sequence_enforcer_program.instruction[
            "check_and_set_sequence_number"
        ](
            sequence_number,
            ctx=Context(
                accounts={
                    "sequence_account": self.get_sequence_address_for_subaccount(
                        subaccount
                    ),
                    "authority": self.wallet.payer.pubkey(),
                }
            ),
        )

        if sequence_number - current_for_subaccount > 0:
            self.set_sequence_number_for_subaccount(subaccount, sequence_number)
        else:
            self.set_sequence_number_for_subaccount(
                subaccount, current_for_subaccount + 1
            )

        return ix

    def get_sequence_number_for_subaccount(self, subaccount: int) -> Optional[int]:
        return self.sequence_number_by_subaccount.get(subaccount, None)

    def get_sequence_init_for_subaccount(self, subaccount: int) -> bool:
        return self.sequence_init_by_subaccount.get(subaccount, False)

    def get_sequence_address_for_subaccount(self, subaccount: int) -> Optional[Pubkey]:
        return self.sequence_address_by_subaccount.get(subaccount, None)

    def get_sequence_bump_for_subaccount(self, subaccount: int) -> Optional[int]:
        return self.sequence_bump_by_subaccount.get(subaccount, None)

    def set_sequence_number_for_subaccount(self, subaccount: int, sequence_number: int):
        self.sequence_number_by_subaccount[subaccount] = sequence_number

    def set_sequence_init_for_subaccount(self, subaccount: int, sequence_init: bool):
        self.sequence_init_by_subaccount[subaccount] = sequence_init

    def set_sequence_address_for_subaccount(self, subaccount: int, address: Pubkey):
        self.sequence_address_by_subaccount[subaccount] = address

    def set_sequence_bump_for_subaccount(self, subaccount: int, bump: int):
        self.sequence_bump_by_subaccount[subaccount] = bump

    def get_resetting_sequence(self):
        return self.resetting_sequence

    def set_resetting_sequence(self, resetting_sequence: bool):
        self.resetting_sequence = resetting_sequence
