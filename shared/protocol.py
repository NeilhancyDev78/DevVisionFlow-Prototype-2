"""Custom binary protocol for DevVisionFlow file transfer.

Protocol header is fixed at 256 bytes:
    [4 bytes]   Magic number: 0x0000DE0F
    [1 byte]    Protocol version: 0x02
    [1 byte]    Message type
    [4 bytes]   Payload length (uint32, big-endian)
    [32 bytes]  SHA-256 hash of payload
    [214 bytes] Reserved / padding
"""

import hashlib
import struct
from dataclasses import dataclass
from typing import Optional

from shared.constants import (
    HEADER_SIZE,
    MAGIC_NUMBER_FULL,
    MSG_ACK,
    MSG_CHUNK,
    MSG_DONE,
    MSG_ERROR,
    MSG_FILE_META,
    MSG_HANDSHAKE,
    PROTOCOL_VERSION,
)


@dataclass
class ProtocolHeader:
    """Represents a parsed protocol header."""

    message_type: int
    payload_length: int
    payload_hash: bytes
    version: int = PROTOCOL_VERSION

    def validate_payload(self, payload: bytes) -> bool:
        """Check whether the payload matches the hash in the header."""
        return hashlib.sha256(payload).digest() == self.payload_hash


# Struct format for the fixed portion of the header (42 bytes used, rest padding)
# 4s = magic, B = version, B = msg_type, I = payload_length, 32s = hash
_HEADER_STRUCT = struct.Struct(">4sBBI32s")
_PADDING_SIZE = HEADER_SIZE - _HEADER_STRUCT.size


def build_header(message_type: int, payload: bytes) -> bytes:
    """Build a 256-byte protocol header for the given payload.

    Args:
        message_type: One of the MSG_* constants.
        payload: The raw payload bytes.

    Returns:
        A 256-byte header as ``bytes``.
    """
    payload_hash = hashlib.sha256(payload).digest()
    header = _HEADER_STRUCT.pack(
        MAGIC_NUMBER_FULL,
        PROTOCOL_VERSION,
        message_type,
        len(payload),
        payload_hash,
    )
    return header + (b"\x00" * _PADDING_SIZE)


def parse_header(data: bytes) -> Optional[ProtocolHeader]:
    """Parse a 256-byte header buffer into a ``ProtocolHeader``.

    Returns ``None`` if the magic number or version is invalid.
    """
    if len(data) < HEADER_SIZE:
        return None

    magic, version, msg_type, payload_length, payload_hash = _HEADER_STRUCT.unpack_from(
        data, 0
    )

    if magic != MAGIC_NUMBER_FULL:
        return None
    if version != PROTOCOL_VERSION:
        return None

    return ProtocolHeader(
        message_type=msg_type,
        payload_length=payload_length,
        payload_hash=payload_hash,
        version=version,
    )


def build_handshake_payload(sender_id: str, encryption_enabled: bool) -> bytes:
    """Build the payload for a HANDSHAKE message."""
    import json

    data = {
        "sender_id": sender_id,
        "encryption": encryption_enabled,
    }
    return json.dumps(data).encode("utf-8")


def parse_handshake_payload(payload: bytes) -> dict:
    """Parse a HANDSHAKE payload."""
    import json

    return json.loads(payload.decode("utf-8"))


def build_file_meta_payload(
    filename: str,
    file_size: int,
    mime_type: str,
    chunk_count: int,
    chunk_size: int,
) -> bytes:
    """Build the payload for a FILE_META message."""
    import json

    data = {
        "filename": filename,
        "file_size": file_size,
        "mime_type": mime_type,
        "chunk_count": chunk_count,
        "chunk_size": chunk_size,
    }
    return json.dumps(data).encode("utf-8")


def parse_file_meta_payload(payload: bytes) -> dict:
    """Parse a FILE_META payload."""
    import json

    return json.loads(payload.decode("utf-8"))


def build_chunk_payload(chunk_index: int, data: bytes) -> bytes:
    """Build the payload for a CHUNK message.

    Format: 4-byte chunk index (uint32 big-endian) + raw chunk data.
    """
    return struct.pack(">I", chunk_index) + data


def parse_chunk_payload(payload: bytes) -> tuple:
    """Parse a CHUNK payload into (chunk_index, chunk_data)."""
    chunk_index = struct.unpack(">I", payload[:4])[0]
    chunk_data = payload[4:]
    return chunk_index, chunk_data


def build_ack_payload(success: bool, message: str = "") -> bytes:
    """Build the payload for an ACK message."""
    import json

    data = {"success": success, "message": message}
    return json.dumps(data).encode("utf-8")


def parse_ack_payload(payload: bytes) -> dict:
    """Parse an ACK payload."""
    import json

    return json.loads(payload.decode("utf-8"))


def build_error_payload(error_code: int, reason: str) -> bytes:
    """Build the payload for an ERROR message."""
    import json

    data = {"error_code": error_code, "reason": reason}
    return json.dumps(data).encode("utf-8")


def parse_error_payload(payload: bytes) -> dict:
    """Parse an ERROR payload."""
    import json

    return json.loads(payload.decode("utf-8"))


def build_done_payload() -> bytes:
    """Build the payload for a DONE message."""
    import json

    return json.dumps({"status": "complete"}).encode("utf-8")


def parse_done_payload(payload: bytes) -> dict:
    """Parse a DONE payload."""
    import json

    return json.loads(payload.decode("utf-8"))
