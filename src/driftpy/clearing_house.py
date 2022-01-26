from dataclasses import dataclass
from typing import TypeVar, Type
from solana.publickey import PublicKey
from anchorpy import Program
from driftpy.types import (
    StateAccount,
    MarketsAccount,
    FundingPaymentHistoryAccount,
    FundingRateHistoryAccount,
    TradeHistoryAccount,
    LiquidationHistoryAccount,
    DepositHistoryAccount,
    CurveHistoryAccount,
)


T = TypeVar("T")


@dataclass
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

    def _find_program_address(self, seeds: list[bytes]) -> tuple[PublicKey, int]:
        return PublicKey.find_program_address(seeds, self.program.program_id)

    async def get_state_account(self) -> StateAccount:
        return await _get_state_account(self.program, self.pdas.state)

    async def get_markets_account(self) -> MarketsAccount:
        return await self.program.account["Markets"].fetch(self.pdas.markets)

    async def get_funding_payment_history_account(self) -> FundingPaymentHistoryAccount:
        return await self.program.account["FundingPaymentHistory"].fetch(
            self.pdas.funding_payment_history
        )

    async def get_funding_rate_history_account(self) -> FundingRateHistoryAccount:
        return await self.program.account["FundingRateHistory"].fetch(
            self.pdas.funding_rate_history
        )

    async def get_trade_history_account(self) -> TradeHistoryAccount:
        return await self.program.account["TradeHistory"].fetch(self.pdas.trade_history)

    async def get_liquidation_history_account(self) -> LiquidationHistoryAccount:
        return await self.program.account["LiquidationHistory"].fetch(
            self.pdas.liquidation_history
        )

    async def get_deposit_history_account(self) -> DepositHistoryAccount:
        return await self.program.account["DepositHistory"].fetch(
            self.pdas.deposit_history
        )

    async def get_curve_history_account(self) -> CurveHistoryAccount:
        return await self.program.account["CurveHistory"].fetch(self.pdas.curve_history)

    @staticmethod
    def _get_state_pubkey(program: Program) -> PublicKey:
        return PublicKey.find_program_address([b"clearing_house"], program.program_id)[
            0
        ]

    @classmethod
    async def create(cls: Type[T], program: Program) -> T:
        state_pubkey = cls._get_state_pubkey(program)
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
