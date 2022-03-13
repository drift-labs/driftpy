from solana.publickey import PublicKey


def get_user_account_public_key_and_nonce(
    program_id: PublicKey, authority: PublicKey
) -> tuple[PublicKey, int]:
    return PublicKey.find_program_address([b"user", bytes(authority)], program_id)


def get_user_orders_account_public_key_and_nonce(
    program_id: PublicKey, authority: PublicKey
) -> tuple[PublicKey, int]:
    user_account_public_key = get_user_account_public_key_and_nonce(
        program_id, authority
    )[0]
    return PublicKey.find_program_address(
        [b"user_orders", bytes(user_account_public_key)], program_id
    )


def get_order_state_account_public_key_and_nonce(
    program_id: PublicKey,
) -> tuple[PublicKey, int]:
    return PublicKey.find_program_address([b"order_state"], program_id)
