from typing import TypeVar, Type
from solana.publickey import PublicKey
from anchorpy import Program
from driftpy.types import StateAccount

T = TypeVar("T")


class ClearingHousePDAs:
    state: PublicKey
    markets: PublicKey
    trade_history: PublicKey
    deposit_history: PublicKey
    funding_payment_history: PublicKey
    funding_rate_history: PublicKey
    liquidation_history: PublicKey
    curve_history: PublicKey


def get_clearing_house_state_account_public_key_and_nonce(
    program_id: PublicKey,
) -> tuple[PublicKey, int]:
    return PublicKey.find_program_address([b"clearing_house"], program_id)


async def _get_state_account(program: Program, state_pubkey: PublicKey) -> StateAccount:
    return await program.account["State"].fetch(state_pubkey)


class ClearingHouse:
    def __init__(self, program: Program, pdas: ClearingHousePDAs):
        self.program = program
        self.pdas = pdas

    def _find_program_address(self, seeds: list[bytes]) -> PublicKey:
        return PublicKey.find_program_address(seeds, self.program.program_id)[0]

    async def get_state_account(self) -> StateAccount:
        return await _get_state_account(self.program, self.pdas.state)

    @classmethod
    async def create(cls: Type[T], program: Program) -> T:
        state_pubkey = PublicKey.find_program_address(
            [b"clearing_house"], program.program_id
        )[0]
        state = await _get_state_account(program, state_pubkey)
        pdas = ClearingHousePDAs(
            state=state_pubkey,
            markets=state.markets,
            trade_history=state.trade_history,
            deposit_history=state.deposit_history,
            funding_payment_history=state.funding_payment_history,
            funding_rate_history=state.funding_rate_history,
            liquidation_history=state.liquidation_history,
            curve_history=state.curve_history,
        )
        return cls(program, pdas)
