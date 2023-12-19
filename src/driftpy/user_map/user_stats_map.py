from typing import Dict, Optional

from solders.pubkey import Pubkey

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.drift_client import DriftClient
from driftpy.types import UserStats, UserStatsAccount


class UserStatsMap:
    def __init__(self, drift_client: DriftClient, bulk_account_loader: Optional[BulkAccountLoader]):
        self.drift_client = drift_client
        if bulk_account_loader is None:
            bulk_account_loader = BulkAccountLoader(drift_client.connection, drift_client.connection.commitment, 0)

        self.bulk_account_loader = bulk_account_loader
        self.user_stats_map: Dict[str, UserStats] = {}

    async def subscribe(self, authorities: list[Pubkey]):
        if self.size() > 0:
            return
        
        await self.drift_client.subscribe()
        await self.sync(authorities)

    def size(self) -> int:
        return len(self.user_stats_map)
    
    def has(self, authority_public_key: str) -> bool:
        return authority_public_key in self.user_stats_map
    
    def get(self, authority_public_key: str) -> UserStats:
        return self.user_stats_map.get(authority_public_key)
    
    def values(self):
        return iter(self.user_stats_map.values())
    
    async def add_user_stat(
        self, 
        authority: Pubkey, 
        user_stats_account: Optional[UserStatsAccount], 
        skip_fetch: Optional[bool]
        ):
        user_stat = UserStats()