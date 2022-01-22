from solana.publickey import PublicKey
from anchorpy import Program
from driftpy.types import StateAccount


class ClearingHousePDAs:
    state: PublicKey
    markets: PublicKey
    trade_history: PublicKey
    deposit_history: PublicKey
    funding_payment_history: PublicKey
    funding_rate_history: PublicKey
    liquidation_history: PublicKey
    curve_history: PublicKey


class ClearingHouse:
    def __init__(self, program: Program, pdas: ClearingHousePDAs):
        self.program = program
        self.pdas = pdas

    def _find_program_address(self, seeds: list[bytes]) -> PublicKey:
        return PublicKey.find_program_address(seeds, self.program.program_id)[0]

    async def get_state_account(self):
        self.program.account["state"].fetch(self.pdas.state)

    @classmethod
    async def create(cls, program: Program) -> "ClearingHouse":
        state_pubkey = PublicKey.find_program_address(
            [b"clearing_house"], program.program_id
        )[0]
        state: StateAccount = program.account["state"].fetch(state_pubkey)
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
