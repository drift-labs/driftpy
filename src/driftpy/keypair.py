from solders.keypair import Keypair
import os
import json
import base58


def load_keypair(private_key):
    # try to load privateKey as a filepath
    if os.path.exists(private_key):
        with open(private_key, "r") as file:
            private_key = file.read().strip()

    key_bytes = None
    if "[" in private_key and "]" in private_key:
        key_bytes = bytes(json.loads(private_key))
    elif "," in private_key:
        key_bytes = bytes(map(int, private_key.split(",")))
    else:
        private_key = private_key.replace(" ", "")
        key_bytes = base58.b58decode(private_key)

    return Keypair.from_bytes(key_bytes)
