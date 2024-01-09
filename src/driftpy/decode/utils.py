def decode_name(bytes_list: list[int]):
    byte_array = bytes(bytes_list)
    return byte_array.decode("utf-8").strip()
