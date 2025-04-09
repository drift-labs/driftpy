import time

from anchorpy.provider import Wallet

from driftpy.accounts import get_spot_market_account
from driftpy.accounts.oracle import get_oracle_price_data_and_slot
from driftpy.constants.numeric_constants import QUOTE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.vaults.helpers import (
    fetch_all_vault_depositors,
    filter_vault_depositors,
    get_all_vaults,
    get_vault_stats,
    get_vaults_program,
)


class VaultClient:
    def __init__(self, connection, wallet=None):
        self.connection = connection
        self.wallet = wallet or Wallet.dummy()
        self.program = None
        self._drift_client = None
        self._spot_decimals_cache = {}
        self._spot_price_cache = {}
        self._vaults_cache = None
        self._all_depositors_cache = None
        self._vault_stats_cache = None
        self._last_refresh_time = 0

    async def initialize(self):
        """Initialize the vault client"""
        self.program = await get_vaults_program(self.connection)
        return self

    @property
    async def drift_client(self):
        """Lazy-loaded drift client"""
        if not self._drift_client:
            self._drift_client = DriftClient(self.connection, wallet=self.wallet)
        return self._drift_client

    async def refresh_cache(self, force=False):
        """Refresh all cached data"""
        current_time = int(time.time())
        # Only refresh if forced or cache is older than 10 minutes
        if (
            force
            or not self._last_refresh_time
            or (current_time - self._last_refresh_time) > 600
        ):
            self._vaults_cache = await get_all_vaults(self.program)
            self._all_depositors_cache = await fetch_all_vault_depositors(self.program)
            self._vault_stats_cache = None  # Clear stats cache since vaults updated
            self._last_refresh_time = current_time

    async def get_all_vaults(self, refresh=False):
        """Get all vaults with optional cache refresh"""
        await self.refresh_cache(force=refresh)
        return self._vaults_cache

    async def get_vault_by_name(self, name, case_sensitive=False, refresh=False):
        """Find a vault by name using cached data"""
        vaults = await self.get_all_vaults(refresh=refresh)

        for vault in vaults:
            vault_name = bytes(vault.account.name).decode("utf-8").rstrip("\x00")
            if case_sensitive:
                if vault_name == name:
                    return vault
            else:
                if vault_name.lower() == name.lower():
                    return vault

        return None

    async def get_all_depositors(self, refresh=False):
        """Get all depositors with optional cache refresh"""
        await self.refresh_cache(force=refresh)
        return (
            self._all_depositors_cache["regular"]
            + self._all_depositors_cache["tokenized"]
        )

    async def get_vault_depositors(self, vault_pubkey, refresh=False):
        """Get depositors for a specific vault using cached data"""
        all_depositors = await self.get_all_depositors(refresh=refresh)
        return await filter_vault_depositors(all_depositors, vault_pubkey)

    async def get_spot_market_decimals_and_price(self, spot_market_index):
        """Get decimals for a spot market with caching"""
        if spot_market_index not in self._spot_decimals_cache:
            client = await self.drift_client
            spot_market = await get_spot_market_account(
                client.program, spot_market_index
            )
            self._spot_decimals_cache[spot_market_index] = spot_market.decimals
            price_data = await get_oracle_price_data_and_slot(
                self.connection, spot_market.oracle, spot_market.oracle_source
            )
            self._spot_price_cache[spot_market_index] = (
                price_data.data.price / QUOTE_PRECISION
            )

        return (
            self._spot_decimals_cache[spot_market_index],
            self._spot_price_cache[spot_market_index],
        )

    async def get_vault_stats(
        self,
        vault_pubkeys=None,
        include_depositors=False,
        normalize_amounts=True,
        refresh=False,
    ):
        """Get stats for vaults (with optional cache refresh)"""
        if refresh or vault_pubkeys is None:
            await self.refresh_cache(force=refresh)

            if vault_pubkeys is None:
                vaults = self._vaults_cache
                vault_pubkeys = [vault.account.pubkey for vault in vaults]

        if (
            self._vault_stats_cache is not None
            and vault_pubkeys is None
            and not refresh
        ):
            stats = self._vault_stats_cache
        else:
            stats = await get_vault_stats(
                self.program, vault_pubkeys, include_depositors=False
            )

            if vault_pubkeys is None:
                self._vault_stats_cache = stats

        if include_depositors:
            all_depositors = await self.get_all_depositors(refresh=refresh)
            for vault in stats:
                vault["depositors"] = await filter_vault_depositors(
                    all_depositors, vault["pubkey"]
                )
                vault["depositor_count"] = len(vault["depositors"])

        if normalize_amounts:
            for vault in stats:
                decimals, spot_price = await self.get_spot_market_decimals_and_price(
                    vault["spot_market_index"]
                )
                vault["true_net_deposits"] = (
                    vault["net_deposits"] / (10**decimals) * spot_price
                )
                vault["true_total_deposits"] = (
                    vault["total_deposits"] / (10**decimals) * spot_price
                )
                vault["true_total_withdraws"] = (
                    vault["total_withdraws"] / (10**decimals) * spot_price
                )

        return stats

    async def get_vault_depositors_with_stats(self, vault_pubkey, refresh=False):
        """Get depositors with additional stats using cached data"""
        depositors = await self.get_vault_depositors(vault_pubkey, refresh=refresh)
        total_shares = sum(getattr(d, "vault_shares", 0) for d in depositors)

        result = []
        for depositor in depositors:
            shares = getattr(depositor, "vault_shares", 0)
            share_percentage = (shares / total_shares * 100) if total_shares else 0

            depositor_info = {
                "depositor": depositor,
                "shares": shares,
                "share_percentage": share_percentage,
            }
            result.append(depositor_info)

        return sorted(result, key=lambda x: x["shares"], reverse=True)

    async def calculate_analytics(self, vault_pubkey=None, refresh=False):
        """Calculate common analytics metrics for vaults"""
        all_stats = await self.get_vault_stats(
            normalize_amounts=True, include_depositors=True, refresh=refresh
        )

        for vault in all_stats:
            if "depositors" in vault and vault["depositors"]:
                shares = [getattr(d, "vault_shares", 0) for d in vault["depositors"]]
                vault["max_share"] = max(shares) if shares else 0
                vault["min_share"] = min(shares) if shares else 0
                vault["share_concentration"] = (
                    vault["max_share"] / sum(shares) if sum(shares) else 0
                )

        analytics = {
            "vaults": all_stats,
            "total_vaults": len(all_stats),
            "total_deposits": sum(v.get("true_net_deposits", 0) for v in all_stats),
            "total_depositors": sum(v.get("depositor_count", 0) for v in all_stats),
            "top_by_deposits": sorted(
                all_stats, key=lambda x: x.get("true_net_deposits", 0), reverse=True
            ),
            "top_by_users": sorted(
                all_stats, key=lambda x: x.get("depositor_count", 0), reverse=True
            ),
        }

        if vault_pubkey:
            vault_stats = next(
                (v for v in all_stats if v["pubkey"] == str(vault_pubkey)), None
            )
            if vault_stats:
                analytics["vault_detail"] = vault_stats

        return analytics
