from typing import Dict, Optional

from construct import Int8ul, Int16ul, Struct
from solders.instruction import Instruction
from solders.pubkey import Pubkey

ED25519_INSTRUCTION_LEN = 16
SIGNATURE_LEN = 64
PUBKEY_LEN = 32
MAGIC_LEN = 4
MESSAGE_SIZE_LEN = 2


def trim_feed_id(feed_id: str) -> str:
    if feed_id.startswith("0x"):
        return feed_id[2:]
    return feed_id


def get_feed_id_uint8_array(feed_id: str) -> bytes:
    trimmed_feed_id = trim_feed_id(feed_id)
    return bytes.fromhex(trimmed_feed_id)


def get_ed25519_args_from_hex(
    hex_str: str, custom_instruction_index: Optional[int] = None
) -> Dict[str, bytes]:
    cleaned_hex = hex_str[2:] if hex_str.startswith("0x") else hex_str
    buffer = bytes.fromhex(cleaned_hex)

    signature_offset = MAGIC_LEN
    public_key_offset = signature_offset + SIGNATURE_LEN
    message_data_size_offset = public_key_offset + PUBKEY_LEN
    message_data_offset = message_data_size_offset + MESSAGE_SIZE_LEN

    signature = buffer[signature_offset : signature_offset + SIGNATURE_LEN]
    public_key = buffer[public_key_offset : public_key_offset + PUBKEY_LEN]
    message_size = buffer[message_data_size_offset] | (
        buffer[message_data_size_offset + 1] << 8
    )
    message = buffer[message_data_offset : message_data_offset + message_size]

    if len(public_key) != PUBKEY_LEN:
        raise ValueError("Invalid public key length")

    if len(signature) != SIGNATURE_LEN:
        raise ValueError("Invalid signature length")

    return {
        "public_key": public_key,
        "signature": signature,
        "message": message,
        "instruction_index": custom_instruction_index,
    }


def read_uint16_le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


ED25519_INSTRUCTION_LAYOUT = Struct(
    "num_signatures" / Int8ul,
    "padding" / Int8ul,
    "signature_offset" / Int16ul,
    "signature_instruction_index" / Int16ul,
    "public_key_offset" / Int16ul,
    "public_key_instruction_index" / Int16ul,
    "message_data_offset" / Int16ul,
    "message_data_size" / Int16ul,
    "message_instruction_index" / Int16ul,
)


def create_minimal_ed25519_verify_ix(
    custom_instruction_index: int,
    message_offset: int,
    custom_instruction_data: bytes,
    magic_len: Optional[int] = None,
) -> Instruction:
    signature_offset = message_offset + (MAGIC_LEN if magic_len is None else magic_len)
    public_key_offset = signature_offset + SIGNATURE_LEN
    message_data_size_offset = public_key_offset + PUBKEY_LEN
    message_data_offset = message_data_size_offset + MESSAGE_SIZE_LEN

    message_data_size = read_uint16_le(
        custom_instruction_data, message_data_size_offset - message_offset
    )

    instruction_data = ED25519_INSTRUCTION_LAYOUT.build(
        dict(
            num_signatures=1,
            padding=0,
            signature_offset=signature_offset,
            signature_instruction_index=custom_instruction_index,
            public_key_offset=public_key_offset,
            public_key_instruction_index=custom_instruction_index,
            message_data_offset=message_data_offset,
            message_data_size=message_data_size,
            message_instruction_index=custom_instruction_index,
        )
    )

    return Instruction(
        program_id=Pubkey.from_string("Ed25519SigVerify111111111111111111111111111"),
        accounts=[],
        data=instruction_data,
    )


# if __name__ == "__main__":
#     test_data_1 = bytes.fromhex(
#         "b9011a82ea7df2f028ab1e3ce5cb8cd641f7efb81d1fb077c20c0eb40f2bf5946d40a014921ffbc2936347da7626d1b99e2b19682114264897594da41f384f5a3e888303f65210bee4fcf5b1cee1e537fabcfd95010297653b94af04d454fc473e94834f8f0175d3c793c0f158a5ee2d0600030b040000000400c17401000000000002e074010000000000019c7401000000000004f6ff2900000004008c255506000000000287d055060000000001158154060000000004f8ff220000000400894e411a00000000023837421a0000000001a4b0401a0000000004f8ff0e0000000400350e5d0e0000000002a0f85d0e00000000012fc65c0e0000000004f8ff2e0000000400ce060b5300000000021d041453000000000110f104530000000004f8ff130000000400a471ee6d00000000021e16f56d000000000156d4e56d0000000004f8ff030000000400ac3b2f010000000002ed4e2f010000000001de272f010000000004f8ff300000000400c6cbaf1200000000020095b01200000000016c0eaf120000000004f8ff5b00000004006ca52d10000000000291432e100000000001fdbc2c100000000004f8ff330000000400bf1d5a0100000000022c2e5a0100000000011d075a010000000004f8ff1200000004000bcb9b9400000000020cdaa2940000000001449893940000000004f8ff"
#     )
#     test_data_2 = bytes.fromhex(
#         "b9011a82e49975a1f2f8ba227141d3d740067554d3a48260d1ac7417d95d43cfe13f47540494ebfe9fc5125f152f72cd9adef0c48260b838e8a50ce177a52ee42b0d0d02f65210bee4fcf5b1cee1e537fabcfd95010297653b94af04d454fc473e94834f310075d3c79300ff5ba5ee2d06000301660000000400ac6b07010000000002d67c07010000000001c85507010000000004f8ff"
#     )

#     ix = create_minimal_ed25519_verify_ix(
#         custom_instruction_index=2,
#         message_offset=12,
#         custom_instruction_data=test_data_1,
#     )
#     correct_data = [1, 0, 16, 0, 2, 0, 80, 0, 2, 0, 114, 0, 143, 1, 2, 0]
#     print(correct_data)
#     print([x for x in ix.data])

#     ix = create_minimal_ed25519_verify_ix(
#         custom_instruction_index=2,
#         message_offset=12,
#         custom_instruction_data=test_data_2,
#     )
#     correct_data = [1, 0, 16, 0, 2, 0, 80, 0, 2, 0, 114, 0, 49, 0, 2, 0]
#     print(correct_data)
#     print([x for x in ix.data])
