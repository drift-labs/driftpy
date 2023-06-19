from dataclasses import dataclass
from driftpy.constants.numeric_constants import *
from driftpy.types import OracleSource

from solana.publickey import PublicKey
from pythclient.pythaccounts import PythPriceAccount
from pythclient.solana import (
    SolanaClient,
    SolanaPublicKey,
)
from solana.rpc.async_api import AsyncClient


def convert_pyth_price(price, scale=1):
    return int(price * PRICE_PRECISION * scale)


@dataclass
class OracleData:
    price: int
    slot: int
    confidence: int
    twap: int
    twap_confidence: int
    has_sufficient_number_of_datapoints: bool


async def get_oracle_data(connection: AsyncClient, address: PublicKey, oracle_source=OracleSource.PYTH()) -> OracleData:
    address = str(address)
    account_key = SolanaPublicKey(address)

    http_endpoint = connection._provider.endpoint_uri
    if "https" in http_endpoint:
        ws_endpoint = http_endpoint.replace("https", "wss")
    elif "http" in http_endpoint:
        ws_endpoint = http_endpoint.replace("http", "wss")
    else:
        print(http_endpoint)
        raise

    solana_client = SolanaClient(endpoint=http_endpoint, ws_endpoint=ws_endpoint)
    if 'Pyth' in str(oracle_source):
        price: PythPriceAccount = PythPriceAccount(account_key, solana_client)
        await price.update()

        # TODO: returns none rn
        # (twap, twac) = (price.derivations.get('TWAPVALUE'), price.derivations.get('TWACVALUE'))
        (twap, twac) = (0, 0)
        scale = 1
        if '1K' in str(oracle_source):
            scale = 1e3
        elif '1M' in str(oracle_source):
            scale = 1e6

        oracle_data = OracleData(
            price=convert_pyth_price(price.aggregate_price_info.price, scale),
            slot=price.last_slot,
            confidence=convert_pyth_price(price.aggregate_price_info.confidence_interval, scale),
            twap=convert_pyth_price(twap, scale),
            twap_confidence=convert_pyth_price(twac,  scale),
            has_sufficient_number_of_datapoints=True,
        )       

        await solana_client.close()

    return oracle_data
