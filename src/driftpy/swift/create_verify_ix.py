from typing import Dict, Optional

from construct import Int8ul, Int16ul, Struct
from solana.constants import ED25519_PROGRAM_ID
from solders.instruction import Instruction

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
        accounts=[],
        program_id=ED25519_PROGRAM_ID,
        data=instruction_data,
    )
