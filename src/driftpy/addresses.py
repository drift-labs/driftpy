from solana.publickey import PublicKey


def get_user_account_public_key_and_nonce(
    program_id: PublicKey, authority: PublicKey
) -> tuple[PublicKey, int]:
    return PublicKey.find_program_address([b"user", bytes(authority)], program_id)
