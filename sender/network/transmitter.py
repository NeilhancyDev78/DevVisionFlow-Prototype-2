"""Socket-based file transmitter for the sender.

Runs in a daemon thread.  Communicates progress back to the main thread
via a ``queue.Queue``.
"""

import logging
import math
import os
import socket
import threading
import queue
from pathlib import Path
from typing import Callable, Optional

from sender.config import SenderConfig
from shared.constants import (
    ACK_TIMEOUT,
    DEFAULT_CHUNK_SIZE,
    HANDSHAKE_TIMEOUT,
    HEADER_SIZE,
    LARGE_FILE_CHUNK_SIZE,
    LARGE_FILE_THRESHOLD,
    MAX_RETRIES,
    MSG_ACK,
    MSG_CHUNK,
    MSG_DONE,
    MSG_ERROR,
    MSG_FILE_META,
    MSG_HANDSHAKE,
)
from shared.encryption import EncryptionContext
from shared.protocol import (
    build_ack_payload,
    build_chunk_payload,
    build_done_payload,
    build_file_meta_payload,
    build_handshake_payload,
    build_header,
    parse_ack_payload,
    parse_header,
)

logger = logging.getLogger(__name__)


class TransferProgress:
    """Data object placed on the progress queue."""

    __slots__ = ("chunks_sent", "total_chunks", "bytes_sent", "total_bytes", "done", "error")

    def __init__(
        self,
        chunks_sent: int = 0,
        total_chunks: int = 0,
        bytes_sent: int = 0,
        total_bytes: int = 0,
        done: bool = False,
        error: str = "",
    ) -> None:
        self.chunks_sent = chunks_sent
        self.total_chunks = total_chunks
        self.bytes_sent = bytes_sent
        self.total_bytes = total_bytes
        self.done = done
        self.error = error

    @property
    def fraction(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.chunks_sent / self.total_chunks


class FileTransmitter:
    """Sends a file to the receiver over the custom protocol."""

    def __init__(self, config: SenderConfig) -> None:
        self.config = config
        self.progress_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._encryption = EncryptionContext(enabled=config.encryption_enabled)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_transferring(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_transfer(self, filepath: Path) -> None:
        """Start a file transfer in a background daemon thread."""
        if self.is_transferring:
            logger.warning("Transfer already in progress")
            return

        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self._transfer_worker,
            args=(filepath,),
            daemon=True,
            name="file-transmitter",
        )
        self._thread.start()

    def cancel(self) -> None:
        """Signal the transfer thread to abort."""
        self._cancel_event.set()

    def get_latest_progress(self) -> Optional[TransferProgress]:
        """Drain the queue and return the most recent progress update."""
        latest = None
        while not self.progress_queue.empty():
            try:
                latest = self.progress_queue.get_nowait()
            except queue.Empty:
                break
        return latest

    # ------------------------------------------------------------------
    # Internal worker
    # ------------------------------------------------------------------

    def _transfer_worker(self, filepath: Path) -> None:
        """Run in a daemon thread -- performs the full transfer sequence."""
        sock = None
        try:
            file_size = filepath.stat().st_size
            chunk_size = (
                LARGE_FILE_CHUNK_SIZE
                if file_size >= LARGE_FILE_THRESHOLD
                else self.config.chunk_size
            )
            total_chunks = math.ceil(file_size / chunk_size) if file_size > 0 else 1

            # Connect
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(HANDSHAKE_TIMEOUT)
            sock.connect((self.config.receiver_host, self.config.receiver_port))

            # --- Handshake ---
            self._send_message(
                sock,
                MSG_HANDSHAKE,
                build_handshake_payload("sender", self.config.encryption_enabled),
            )
            self._wait_for_ack(sock)

            # --- File metadata ---
            import mimetypes

            mime = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"
            meta_payload = build_file_meta_payload(
                filename=filepath.name,
                file_size=file_size,
                mime_type=mime,
                chunk_count=total_chunks,
                chunk_size=chunk_size,
            )
            self._send_message(sock, MSG_FILE_META, meta_payload)
            self._wait_for_ack(sock)

            # --- Chunks ---
            sock.settimeout(ACK_TIMEOUT)
            bytes_sent = 0
            with open(filepath, "rb") as f:
                for chunk_idx in range(total_chunks):
                    if self._cancel_event.is_set():
                        logger.info("Transfer cancelled by user")
                        self.progress_queue.put(
                            TransferProgress(error="Cancelled by user")
                        )
                        return

                    raw_data = f.read(chunk_size)
                    if not raw_data:
                        break

                    data = self._encryption.encrypt(raw_data)
                    chunk_payload = build_chunk_payload(chunk_idx, data)
                    self._send_with_retry(sock, MSG_CHUNK, chunk_payload)

                    bytes_sent += len(raw_data)
                    self.progress_queue.put(
                        TransferProgress(
                            chunks_sent=chunk_idx + 1,
                            total_chunks=total_chunks,
                            bytes_sent=bytes_sent,
                            total_bytes=file_size,
                        )
                    )

            # --- Done ---
            self._send_message(sock, MSG_DONE, build_done_payload())
            self._wait_for_ack(sock)

            self.progress_queue.put(
                TransferProgress(
                    chunks_sent=total_chunks,
                    total_chunks=total_chunks,
                    bytes_sent=file_size,
                    total_bytes=file_size,
                    done=True,
                )
            )
            logger.info("Transfer complete: %s", filepath.name)

        except Exception as exc:
            logger.error("Transfer failed: %s", exc)
            self.progress_queue.put(TransferProgress(error=str(exc)))
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _send_message(self, sock: socket.socket, msg_type: int, payload: bytes) -> None:
        """Send a header + payload over the socket."""
        header = build_header(msg_type, payload)
        sock.sendall(header + payload)

    def _wait_for_ack(self, sock: socket.socket) -> dict:
        """Block until an ACK header + payload is received."""
        header_data = self._recv_exact(sock, HEADER_SIZE)
        hdr = parse_header(header_data)
        if hdr is None:
            raise ConnectionError("Invalid header received while waiting for ACK")
        payload = self._recv_exact(sock, hdr.payload_length)
        if hdr.message_type == MSG_ERROR:
            from shared.protocol import parse_error_payload

            err = parse_error_payload(payload)
            raise ConnectionError(f"Receiver error: {err.get('reason', 'unknown')}")
        if hdr.message_type != MSG_ACK:
            raise ConnectionError(f"Expected ACK, got message type {hdr.message_type}")
        ack = parse_ack_payload(payload)
        if not ack.get("success", False):
            raise ConnectionError(f"Receiver NACK: {ack.get('message', '')}")
        return ack

    def _send_with_retry(self, sock: socket.socket, msg_type: int, payload: bytes) -> None:
        """Send a message with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                self._send_message(sock, msg_type, payload)
                self._wait_for_ack(sock)
                return
            except (socket.timeout, ConnectionError) as exc:
                logger.warning(
                    "Chunk send attempt %d/%d failed: %s", attempt + 1, MAX_RETRIES, exc
                )
                if attempt == MAX_RETRIES - 1:
                    raise

    @staticmethod
    def _recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
        """Read exactly *num_bytes* from the socket."""
        buf = bytearray()
        while len(buf) < num_bytes:
            chunk = sock.recv(num_bytes - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed while reading")
            buf.extend(chunk)
        return bytes(buf)
