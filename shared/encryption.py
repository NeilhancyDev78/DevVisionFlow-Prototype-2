"""Encryption utilities using AES-256-GCM with X25519 key exchange.

Provides optional per-chunk authenticated encryption for the file transfer
protocol.  When encryption is disabled the wrapper functions become
pass-throughs so the rest of the code does not need conditional branches.
"""

import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes, serialization

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography library not installed -- encryption will be unavailable"
    )

# Nonce size for AES-GCM (96 bits recommended by NIST)
NONCE_SIZE: int = 12
AES_KEY_LENGTH: int = 32  # 256 bits


def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate an X25519 key-pair and return (private_bytes, public_bytes).

    Raises:
        RuntimeError: If the ``cryptography`` library is not installed.
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library is required for encryption")

    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes


def derive_shared_key(private_bytes: bytes, peer_public_bytes: bytes) -> bytes:
    """Perform X25519 key exchange and derive a 256-bit AES key via HKDF.

    Args:
        private_bytes: 32-byte raw private key.
        peer_public_bytes: 32-byte raw public key from the remote peer.

    Returns:
        32-byte derived AES key.
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library is required for encryption")

    private_key = X25519PrivateKey.from_private_bytes(private_bytes)
    peer_public_key = X25519PublicKey.from_public_bytes(peer_public_bytes)
    shared_secret = private_key.exchange(peer_public_key)

    aes_key = HKDF(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=None,
        info=b"devvisionflow-v2-file-transfer",
    ).derive(shared_secret)

    return aes_key


def encrypt_chunk(aes_key: bytes, plaintext: bytes) -> bytes:
    """Encrypt a chunk using AES-256-GCM.

    The returned ciphertext has the nonce prepended:
        nonce (12 bytes) || ciphertext+tag

    Args:
        aes_key: 32-byte AES key.
        plaintext: Data to encrypt.

    Returns:
        Encrypted bytes with prepended nonce.
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library is required for encryption")

    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_chunk(aes_key: bytes, data: bytes) -> bytes:
    """Decrypt a chunk encrypted with ``encrypt_chunk``.

    Args:
        aes_key: 32-byte AES key.
        data: nonce (12 bytes) || ciphertext+tag

    Returns:
        Decrypted plaintext bytes.
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library is required for encryption")

    nonce = data[:NONCE_SIZE]
    ciphertext = data[NONCE_SIZE:]
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ciphertext, None)


class EncryptionContext:
    """High-level wrapper that can be enabled or disabled transparently."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled and CRYPTO_AVAILABLE
        self._aes_key: bytes = b""
        self._private_bytes: bytes = b""
        self._public_bytes: bytes = b""

        if self.enabled:
            self._private_bytes, self._public_bytes = generate_keypair()

    @property
    def public_key_bytes(self) -> bytes:
        """Return the local public key bytes for exchange."""
        return self._public_bytes

    def complete_handshake(self, peer_public_bytes: bytes) -> None:
        """Derive the shared AES key after receiving the peer's public key."""
        if not self.enabled:
            return
        self._aes_key = derive_shared_key(self._private_bytes, peer_public_bytes)
        logger.info("Encryption handshake complete -- AES key derived")

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data if encryption is enabled, otherwise return as-is."""
        if not self.enabled:
            return data
        return encrypt_chunk(self._aes_key, data)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data if encryption is enabled, otherwise return as-is."""
        if not self.enabled:
            return data
        return decrypt_chunk(self._aes_key, data)
