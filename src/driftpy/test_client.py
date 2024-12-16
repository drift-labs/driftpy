from typing import List, Optional

from anchorpy.provider import Wallet
from icecream import ic
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.types import TxOpts
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import TransactionVersion

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts import (
    OracleInfo,
    TxParams,
)
from driftpy.accounts.polling.drift_client import PollingDriftClientAccountSubscriber
from driftpy.admin import Admin
from driftpy.constants.config import (
    DriftEnv,
)
from driftpy.drift_client import DEFAULT_TX_OPTIONS, JitoParams
from driftpy.tx.types import TxSender, TxSigAndSlot


class TestClient(Admin):
    def __init__(
        self,
        connection: AsyncClient,
        wallet: Keypair | Wallet,
        env: DriftEnv | None = "mainnet",
        opts: TxOpts = DEFAULT_TX_OPTIONS,
        authority: Pubkey | None = None,
        account_subscription: AccountSubscriptionConfig = AccountSubscriptionConfig.default(),
        perp_market_indexes: list[int] | None = None,
        spot_market_indexes: list[int] | None = None,
        oracle_infos: list[OracleInfo] | None = None,
        tx_params: TxParams | None = None,
        tx_version: TransactionVersion | None = None,
        tx_sender: TxSender | None = None,
        active_sub_account_id: int | None = None,
        sub_account_ids: list[int] | None = None,
        market_lookup_table: Pubkey | None = None,
        jito_params: JitoParams | None = None,
        tx_sender_blockhash_commitment: Commitment | None = None,
        enforce_tx_sequencing: bool = False,
    ):
        if account_subscription.type != "polling":
            raise ValueError("Test client must be polling")
        super().__init__(
            connection=connection,
            wallet=wallet,
            env=env,
            opts=opts,
            authority=authority,
            account_subscription=account_subscription,
            perp_market_indexes=perp_market_indexes,
            spot_market_indexes=spot_market_indexes,
            oracle_infos=oracle_infos,
            tx_params=tx_params,
            tx_version=tx_version,
            tx_sender=tx_sender,
            active_sub_account_id=active_sub_account_id,
            sub_account_ids=sub_account_ids,
            market_lookup_table=market_lookup_table,
            jito_params=jito_params,
            tx_sender_blockhash_commitment=tx_sender_blockhash_commitment,
            enforce_tx_sequencing=enforce_tx_sequencing,
        )

    async def send_ixs(
        self,
        ixs: Instruction | list[Instruction],
        additional_signers: Optional[List[Keypair]] = None,
        pre_signed: bool = False,
    ) -> TxSigAndSlot:
        if not isinstance(self.account_subscriber, PollingDriftClientAccountSubscriber):
            raise ValueError("Account subscriber must be polling")

        tx_sig_and_slot = await super().send_ixs(
            ixs=ixs,
            signers=additional_signers,
            lookup_tables=[],
        )
        ic(tx_sig_and_slot)

        last_fetched_slot = self.account_subscriber.bulk_account_loader.most_recent_slot
        await self.fetch_accounts()

        while last_fetched_slot < tx_sig_and_slot.slot:
            ic(last_fetched_slot, tx_sig_and_slot.slot)
            await self.fetch_accounts()
            last_fetched_slot = (
                self.account_subscriber.bulk_account_loader.most_recent_slot
            )

        return tx_sig_and_slot
