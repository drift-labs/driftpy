from solders.pubkey import Pubkey


def int_to_le_bytes(a: int):
    return a.to_bytes(2, "little")


def get_perp_market_public_key(
    program_id: Pubkey,
    market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"perp_market", int_to_le_bytes(market_index)], program_id
    )[0]


def get_insurance_fund_vault_public_key(
    program_id: Pubkey,
    spot_market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"insurance_fund_vault", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_insurance_fund_stake_public_key(
    program_id: Pubkey,
    authority: Pubkey,
    spot_market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"insurance_fund_stake", bytes(authority), int_to_le_bytes(spot_market_index)],
        program_id,
    )[0]


def get_spot_market_public_key(
    program_id: Pubkey,
    spot_market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"spot_market", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_spot_market_vault_public_key(
    program_id: Pubkey,
    spot_market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"spot_market_vault", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_spot_market_vault_authority_public_key(
    program_id: Pubkey,
    spot_market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"spot_market_vault_authority", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_state_public_key(
    program_id: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address([b"drift_state"], program_id)[0]


def get_drift_client_signer_public_key(
    program_id: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address([b"drift_signer"], program_id)[0]


def get_user_stats_account_public_key(
    program_id: Pubkey,
    authority: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address([b"user_stats", bytes(authority)], program_id)[0]


def get_user_account_public_key(
    program_id: Pubkey,
    authority: Pubkey,
    sub_account_id=0,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"user", bytes(authority), int_to_le_bytes(sub_account_id)], program_id
    )[0]


def get_prelaunch_oracle_public_key(program_id: Pubkey, market_index: int) -> Pubkey:
    return Pubkey.find_program_address(
        [b"prelaunch_oracle", int_to_le_bytes(market_index)], program_id
    )[0]


def get_serum_open_orders_public_key(
    program_id: Pubkey,
    market: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"serum_open_orders", bytes(market)], program_id
    )[0]


def get_serum_signer_public_key(
    program_id: Pubkey,
    market: Pubkey,
    nonce: int,
) -> Pubkey:
    return Pubkey.create_program_address(
        [bytes(market), int_to_le_bytes(nonce)], program_id
    )


def get_serum_fulfillment_config_public_key(
    program_id: Pubkey,
    market: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"serum_fulfillment_config", bytes(market)], program_id
    )[0]


def get_phoenix_fulfillment_config_public_key(
    program_id: Pubkey,
    market: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"phoenix_fulfillment_config", bytes(market)], program_id
    )[0]


def get_sequencer_public_key_and_bump(
    program_id: Pubkey, payer: Pubkey, subaccount_id: int
) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address(
        [(str(subaccount_id)).encode(), bytes(payer)], program_id
    )


def get_high_leverage_mode_config_public_key(program_id: Pubkey) -> Pubkey:
    return Pubkey.find_program_address([b"high_leverage_mode_config"], program_id)[0]


def get_protected_maker_mode_config_public_key(program_id: Pubkey) -> Pubkey:
    return Pubkey.find_program_address([b"protected_maker_mode_config"], program_id)[0]


def get_rfq_user_account_public_key(
    program_id: Pubkey,
    user_account_public_key: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address(
        [b"RFQ", bytes(user_account_public_key)], program_id
    )[0]


def get_signed_msg_user_account_public_key(
    program_id: Pubkey,
    authority: Pubkey,
) -> Pubkey:
    return Pubkey.find_program_address([b"SIGNED_MSG", bytes(authority)], program_id)[0]


def get_if_rebalance_config_public_key(
    program_id: Pubkey,
    in_market_index: int,
    out_market_index: int,
) -> Pubkey:
    return Pubkey.find_program_address(
        [
            b"if_rebalance_config",
            int_to_le_bytes(in_market_index),
            int_to_le_bytes(out_market_index),
        ],
        program_id,
    )[0]
