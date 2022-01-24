from pytest import fixture, mark
from solana.publickey import PublicKey
from solana.keypair import Keypair
from anchorpy import Program, Provider, WorkspaceType

from driftpy.admin import Admin
from driftpy.types import StateAccount


@fixture(scope="module")
def program(workspace: WorkspaceType) -> Program:
    return workspace["clearing_house"]


@fixture(scope="module")
async def clearing_house(program: Program, usdc_mint: Keypair) -> Admin:
    await Admin.initialize(program, usdc_mint.public_key, admin_controls_prices=True)
    return await Admin.from_(program.program_id, program.provider)


@fixture(scope="module")
async def state(clearing_house: Admin) -> StateAccount:
    return await clearing_house.get_state_account()


@mark.asyncio
async def test_state(state: StateAccount, provider: Provider):
    assert state.admin == provider.wallet.public_key
