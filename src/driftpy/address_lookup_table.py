from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.address_lookup_table_account import AddressLookupTableAccount

LOOKUP_TABLE_META_SIZE = 56


async def get_address_lookup_table(
    connection: AsyncClient, pubkey: Pubkey
) -> AddressLookupTableAccount:
    account_info = await connection.get_account_info(pubkey)
    return decode_address_lookup_table(pubkey, account_info.value.data)


def decode_address_lookup_table(pubkey: Pubkey, data: bytes):
    data_len = len(data)

    addresses = []
    i = LOOKUP_TABLE_META_SIZE
    while i < data_len:
        addresses.append(Pubkey.from_bytes(data[i : i + 32]))
        i += 32

    return AddressLookupTableAccount(pubkey, addresses)
