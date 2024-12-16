from anchorpy.provider import Wallet
from pytest import mark
from solana.rpc.async_api import AsyncClient
from solders.signature import Signature

from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber


@mark.asyncio
async def test_events_parser():
    connection = AsyncClient("https://api.mainnet-beta.solana.com")
    drift_client = DriftClient(connection, Wallet.dummy())

    event_subscriber = EventSubscriber(drift_client.connection, drift_client.program)

    tx = await connection.get_transaction(
        Signature.from_string(
            "3JRzMVquzXXmbV7cPMxiMRQp25scFFkYpsntWjMJQv3i4sMZyVXAGi6X2vAHNkqH1mkNtLvpp4oT6iorzZgLkYNY"
        ),
        max_supported_transaction_version=0,
    )
    if not tx.value:
        raise ValueError("tx.value is None")
    if not tx.value.transaction.meta:
        raise ValueError("tx.value.transaction.meta is None")
    if not tx.value.transaction.meta.log_messages:
        raise ValueError("tx.value.transaction.meta.log_messages is None")

    logs = tx.value.transaction.meta.log_messages

    events = event_subscriber.parse_events_from_logs(
        Signature.from_string(
            "3JRzMVquzXXmbV7cPMxiMRQp25scFFkYpsntWjMJQv3i4sMZyVXAGi6X2vAHNkqH1mkNtLvpp4oT6iorzZgLkYNY"
        ),
        tx.value.slot,
        logs,
    )

    print(events)
