
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.user_map.types import ConfigType, Subscription


class CachedSubscription(Subscription):
    def get_subscription_config(self):
        return AccountSubscriptionConfig(ConfigType.CACHED.value)
