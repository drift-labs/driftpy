from struct import pack_into

MAX_LENGTH = 32


def encode_name(name: str) -> list[int]:
    if len(name) > 32:
        raise Exception("name too long")

    name_bytes = bytearray(32)
    pack_into(f"{len(name)}s", name_bytes, 0, name.encode("utf-8"))
    offset = len(name)
    for _ in range(32 - len(name)):
        pack_into("1s", name_bytes, offset, " ".encode("utf-8"))
        offset += 1

    str_name_bytes = name_bytes.hex()
    name_byte_array = []
    for i in range(0, len(str_name_bytes), 2):
        name_byte_array.append(int(str_name_bytes[i : i + 2], 16))

    return name_byte_array
