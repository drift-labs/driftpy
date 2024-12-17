import asyncio

import jsonrpcclient
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.transaction import Signature
from solders.pubkey import Pubkey
from solders.rpc.responses import (
    RpcConfirmedTransactionStatusWithSignature,
)


async def fetch_logs(
    connection: AsyncClient,
    address: Pubkey,
    commitment: Commitment,
    before_tx: Signature = None,
    until_tx: Signature = None,
    limit: int = None,
    batch_size: int = None,
) -> list[(Signature, int, list[str])]:
    response = await connection.get_signatures_for_address(
        address, before_tx, until_tx, limit, commitment
    )

    if response.value is None:
        raise Exception("Error with get_signature_for_address")

    signatures = response.value

    sorted_signatures = sorted(signatures, key=lambda x: x.slot)

    filtered_signatures = list(
        filter(lambda signature: not signature.err, sorted_signatures)
    )

    if len(filtered_signatures) == 0:
        return []

    batch_size = batch_size if batch_size is not None else 25
    chunked_signatures = chunk(filtered_signatures, batch_size)

    chunked_transactions_logs = await asyncio.gather(
        *[
            fetch_transactions(connection, signatures, commitment)
            for signatures in chunked_signatures
        ]
    )

    return [
        transaction_logs
        for transactions_logs in chunked_transactions_logs
        for transaction_logs in transactions_logs
    ]


async def fetch_transactions(
    connection: AsyncClient,
    signatures: list[RpcConfirmedTransactionStatusWithSignature],
    commitment: Commitment,
) -> list[(Signature, int, list[str])]:
    rpc_requests = []
    for signature in signatures:
        rpc_request = jsonrpcclient.request(
            "getTransaction",
            (
                str(signature.signature),
                {"commitment": commitment, "maxSupportedTransactionVersion": 0},
            ),
        )
        rpc_requests.append(rpc_request)

    try:
        post = connection._provider.session.post(
            connection._provider.endpoint_uri,
            json=rpc_requests,
            headers={"content-encoding": "gzip"},
        )
        resp = await asyncio.wait_for(post, timeout=10)
    except asyncio.TimeoutError:
        print("request to rpc timed out")
        return []

    parsed_resp = jsonrpcclient.parse(resp.json())

    if isinstance(parsed_resp, jsonrpcclient.Error):
        raise ValueError(f"Error fetching transactions: {parsed_resp.message}")
    if not isinstance(parsed_resp, jsonrpcclient.Ok):
        raise ValueError(f"Error fetching transactions - not ok: {parsed_resp}")

    response = []
    for rpc_result in parsed_resp:
        if rpc_result.result:
            tx_sig = rpc_result.result["transaction"]["signatures"][0]
            slot = rpc_result.result["slot"]
            logs = rpc_result.result["meta"]["logMessages"]
            response.append((tx_sig, slot, logs))

    return response


def chunk(array, size):
    return [array[i : i + size] for i in range(0, len(array), size)]
