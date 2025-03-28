import base64
import hashlib
import random
import string


def digest_signature(signature: bytes) -> str:
    """
    Create a SHA-256 hash of a signature and return it as a base64 string.

    Args:
        signature: The signature bytes to hash

    Returns:
        Base64-encoded SHA-256 hash of the signature
    """
    hash_object = hashlib.sha256(signature)
    return base64.b64encode(hash_object.digest()).decode("utf-8")


def generate_signed_msg_uuid(length=8) -> bytes:
    """
    Generate a random string similar to nanoid with specified length and convert to bytes.

    Args:
        length: Length of the random string to generate (default: 8)

    Returns:
        Bytes representation of the generated random string
    """
    chars = string.ascii_letters + string.digits + "-_"  # nanoid alphabet
    random_id = "".join(random.choice(chars) for _ in range(length))
    return random_id.encode("utf-8")
