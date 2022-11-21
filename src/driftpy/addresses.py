from solana.publickey import PublicKey


def int_to_le_bytes(a: int):
    return a.to_bytes(2, "little")


def get_perp_market_public_key(
    program_id: PublicKey,
    market_index: int,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"perp_market", int_to_le_bytes(market_index)], program_id
    )[0]


def get_insurance_fund_vault_public_key(
    program_id: PublicKey,
    spot_market_index: int,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"insurance_fund_vault", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_insurance_fund_stake_public_key(
    program_id: PublicKey,
    authority: PublicKey,
    spot_market_index: int,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"insurance_fund_stake", bytes(authority), int_to_le_bytes(spot_market_index)],
        program_id,
    )[0]


def get_spot_market_public_key(
    program_id: PublicKey,
    spot_market_index: int,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"spot_market", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_spot_market_vault_public_key(
    program_id: PublicKey,
    spot_market_index: int,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"spot_market_vault", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_spot_market_vault_authority_public_key(
    program_id: PublicKey,
    spot_market_index: int,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"spot_market_vault_authority", int_to_le_bytes(spot_market_index)], program_id
    )[0]


def get_state_public_key(
    program_id: PublicKey,
) -> PublicKey:
    return PublicKey.find_program_address([b"drift_state"], program_id)[0]


def get_clearing_house_signer_public_key(
    program_id: PublicKey,
) -> PublicKey:
    return PublicKey.find_program_address([b"drift_signer"], program_id)[0]


def get_user_stats_account_public_key(
    program_id: PublicKey,
    authority: PublicKey,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"user_stats", bytes(authority)], program_id
    )[0]


def get_user_account_public_key(
    program_id: PublicKey,
    authority: PublicKey,
    user_id=0,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"user", bytes(authority), int_to_le_bytes(user_id)], program_id
    )[0]


# program = PublicKey("9jwr5nC2f9yAraXrg4UzHXmCX3vi9FQkjD6p9e8bRqNa")
# auth = PublicKey("D78cqss3dbU1aJAs5qeuhLi8Rqa2CL4Kzkr3VzdgN5F6")
# == EjQ8rFmR4hd9faX1TYLkqCTsAkyjJ4qUKBuagtmVG3cP
# get_user_account_public_key(
#     program,
#     auth
# )
