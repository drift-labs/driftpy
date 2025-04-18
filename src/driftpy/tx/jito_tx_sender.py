raise ImportError(
    "The jito_tx_sender module is deprecated and has been removed in driftpy. "
)


class JitoTxSender:
    def __init__(
        self,
        drift_client,
        opts,
        block_engine_url,
        jito_keypair,
        blockhash_commitment,
        blockhash_refresh_interval_secs=None,
        tip_amount=None,
    ):
        raise NotImplementedError(
            "JitoTxSender is deprecated and has been removed in driftpy."
        )
