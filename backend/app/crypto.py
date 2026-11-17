import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def derive_kek(
    master_password: str, salt: bytes
) -> bytes:  # function to derive Key Encryption Key
    """Stretch the master password into a 32-byte key."""
    return Scrypt(
        salt=salt, length=32, n=2**15, r=8, p=1
    ).derive(  # n=2^15 means CPU/memory cost r=8 block size parameters p=1 parallelization parameter
        master_password.encode()  # master password is converted to binary as script works with binary
    )


def encrypt(key: bytes, data: bytes) -> bytes:
    """AES-256 GCM. Output is nonce(12 bytes)+ciphertext+authentication tag"""
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, None)


def decrypt(key: bytes, blob: bytes) -> bytes:
    """Raises crytpography.exceptions.InvalidTag if the key is wrong or data is altered"""
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


def new_recovery_key() -> tuple[bytes, str]:
    raw = os.urandom(32)
    text = base64.b32encode(raw).decode().rstrip("=")
    return raw, "-".join(text[i : i + 4] for i in range(0, len(text), 4))


def parse_recover_key(text: str) -> bytes:
    s = text.replace("-", "").replace(" ", "").upper()
    s += "=" * (-len(s) % 8)
    return base64.b32decode(s)
