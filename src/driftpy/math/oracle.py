from dataclasses import dataclass
from driftpy.constants.numeric_constants import *

from solana.publickey import PublicKey
from pythclient.pythaccounts import PythPriceAccount
from pythclient.solana import (
    SolanaClient,
    SolanaPublicKey,
)
from solana.rpc.async_api import AsyncClient


def convert_pyth_price(price):
    return int(price * PRICE_PRECISION)


@dataclass
class OracleData:
    price: int
    slot: int
    confidence: int
    twap: int
    twap_confidence: int
    has_sufficient_number_of_datapoints: bool


async def get_oracle_data(connection: AsyncClient, address: PublicKey) -> OracleData:
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
    price: PythPriceAccount = PythPriceAccount(account_key, solana_client)
    await price.update()

    # TODO: returns none rn
    # (twap, twac) = (price.derivations.get('TWAPVALUE'), price.derivations.get('TWACVALUE'))
    (twap, twac) = (0, 0)

    oracle_data = OracleData(
        price=convert_pyth_price(price.aggregate_price_info.price),
        slot=price.last_slot,
        confidence=convert_pyth_price(price.aggregate_price_info.confidence_interval),
        twap=convert_pyth_price(twap),
        twap_confidence=convert_pyth_price(twac),
        has_sufficient_number_of_datapoints=True,
    )

    await solana_client.close()

    return oracle_data
