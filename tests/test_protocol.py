"""Tests for the shared protocol module."""

import sys
import os
import unittest

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.constants import (
    HEADER_SIZE,
    MSG_ACK,
    MSG_CHUNK,
    MSG_DONE,
    MSG_ERROR,
    MSG_FILE_META,
    MSG_HANDSHAKE,
)
from shared.protocol import (
    ProtocolHeader,
    build_ack_payload,
    build_chunk_payload,
    build_done_payload,
    build_error_payload,
    build_file_meta_payload,
    build_handshake_payload,
    build_header,
    parse_ack_payload,
    parse_chunk_payload,
    parse_done_payload,
    parse_error_payload,
    parse_file_meta_payload,
    parse_handshake_payload,
    parse_header,
)


class TestBuildAndParseHeader(unittest.TestCase):
    """Round-trip tests for header serialisation."""

    def test_header_length(self) -> None:
        payload = b"hello"
        header = build_header(MSG_HANDSHAKE, payload)
        self.assertEqual(len(header), HEADER_SIZE)

    def test_roundtrip(self) -> None:
        payload = b"test payload data"
        header = build_header(MSG_FILE_META, payload)
        parsed = parse_header(header)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.message_type, MSG_FILE_META)
        self.assertEqual(parsed.payload_length, len(payload))
        self.assertTrue(parsed.validate_payload(payload))

    def test_invalid_magic(self) -> None:
        header = b"\x00" * HEADER_SIZE
        self.assertIsNone(parse_header(header))

    def test_short_header(self) -> None:
        self.assertIsNone(parse_header(b"\x00" * 10))

    def test_payload_integrity_mismatch(self) -> None:
        payload = b"original"
        header = build_header(MSG_CHUNK, payload)
        parsed = parse_header(header)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertFalse(parsed.validate_payload(b"tampered"))


class TestHandshakePayload(unittest.TestCase):
    def test_roundtrip(self) -> None:
        payload = build_handshake_payload("sender-1", True)
        result = parse_handshake_payload(payload)
        self.assertEqual(result["sender_id"], "sender-1")
        self.assertTrue(result["encryption"])

    def test_no_encryption(self) -> None:
        payload = build_handshake_payload("s2", False)
        result = parse_handshake_payload(payload)
        self.assertFalse(result["encryption"])


class TestFileMetaPayload(unittest.TestCase):
    def test_roundtrip(self) -> None:
        payload = build_file_meta_payload(
            filename="test.txt",
            file_size=12345,
            mime_type="text/plain",
            chunk_count=1,
            chunk_size=65536,
        )
        result = parse_file_meta_payload(payload)
        self.assertEqual(result["filename"], "test.txt")
        self.assertEqual(result["file_size"], 12345)
        self.assertEqual(result["mime_type"], "text/plain")
        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(result["chunk_size"], 65536)


class TestChunkPayload(unittest.TestCase):
    def test_roundtrip(self) -> None:
        data = b"\x00\x01\x02\x03" * 100
        payload = build_chunk_payload(42, data)
        idx, parsed_data = parse_chunk_payload(payload)
        self.assertEqual(idx, 42)
        self.assertEqual(parsed_data, data)

    def test_empty_chunk(self) -> None:
        payload = build_chunk_payload(0, b"")
        idx, parsed_data = parse_chunk_payload(payload)
        self.assertEqual(idx, 0)
        self.assertEqual(parsed_data, b"")


class TestAckPayload(unittest.TestCase):
    def test_success(self) -> None:
        payload = build_ack_payload(True, "OK")
        result = parse_ack_payload(payload)
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "OK")

    def test_failure(self) -> None:
        payload = build_ack_payload(False, "Bad chunk")
        result = parse_ack_payload(payload)
        self.assertFalse(result["success"])


class TestErrorPayload(unittest.TestCase):
    def test_roundtrip(self) -> None:
        payload = build_error_payload(42, "disk full")
        result = parse_error_payload(payload)
        self.assertEqual(result["error_code"], 42)
        self.assertEqual(result["reason"], "disk full")


class TestDonePayload(unittest.TestCase):
    def test_roundtrip(self) -> None:
        payload = build_done_payload()
        result = parse_done_payload(payload)
        self.assertEqual(result["status"], "complete")


if __name__ == "__main__":
    unittest.main()
