from solana.publickey import PublicKey

def int_to_le_bytes(a: int):
    return a.to_bytes(8, 'little')

def get_market_public_key(
    program_id: PublicKey, 
    market_index: int, 
) -> PublicKey: 
    return PublicKey.find_program_address(
        [b"market", int_to_le_bytes(market_index)], 
        program_id
    )[0]

def get_bank_public_key(
    program_id: PublicKey, 
    bank_index: int, 
) -> PublicKey: 
    return PublicKey.find_program_address(
        [b"bank", int_to_le_bytes(bank_index)], 
        program_id
    )[0]

def get_bank_vault_public_key(
    program_id: PublicKey, 
    bank_index: int, 
) -> PublicKey: 
    return PublicKey.find_program_address(
        [b"bank_vault", int_to_le_bytes(bank_index)], 
        program_id
    )[0]

def get_bank_vault_authority_public_key(
    program_id: PublicKey, 
    bank_index: int, 
) -> PublicKey: 
    return PublicKey.find_program_address(
        [b"bank_vault_authority", int_to_le_bytes(bank_index)], 
        program_id
    )[0]

def get_state_public_key(
    program_id: PublicKey, 
) -> PublicKey: 
    return PublicKey.find_program_address(
        [b"clearing_house"],
        program_id
    )[0]

def get_user_account_public_key(
    program_id: PublicKey, 
    authority: PublicKey, 
    user_id = 0,
) -> PublicKey:
    return PublicKey.find_program_address(
        [b"user", bytes(authority), bytes([user_id])],
        program_id
    )[0]

# program = PublicKey("9jwr5nC2f9yAraXrg4UzHXmCX3vi9FQkjD6p9e8bRqNa")
# auth = PublicKey("D78cqss3dbU1aJAs5qeuhLi8Rqa2CL4Kzkr3VzdgN5F6")
# == EjQ8rFmR4hd9faX1TYLkqCTsAkyjJ4qUKBuagtmVG3cP
# get_user_account_public_key(
#     program, 
#     auth
# )
