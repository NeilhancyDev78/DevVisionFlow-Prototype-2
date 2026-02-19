"""TCP socket listener for the receiver.

Accepts incoming connections from the sender, reads protocol headers,
streams file chunks to disk, and sends ACKs for flow control.
"""

import logging
import socket
import threading
from pathlib import Path
from typing import Callable, Optional

from receiver.config import ReceiverConfig
from shared.constants import (
    HEADER_SIZE,
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
    build_error_payload,
    build_header,
    parse_chunk_payload,
    parse_done_payload,
    parse_file_meta_payload,
    parse_handshake_payload,
    parse_header,
)

logger = logging.getLogger(__name__)


class ReceivedFileInfo:
    """Metadata about a file currently being received."""

    __slots__ = (
        "filename",
        "file_size",
        "mime_type",
        "chunk_count",
        "chunk_size",
        "chunks_received",
        "save_path",
    )

    def __init__(self) -> None:
        self.filename: str = ""
        self.file_size: int = 0
        self.mime_type: str = ""
        self.chunk_count: int = 0
        self.chunk_size: int = 0
        self.chunks_received: int = 0
        self.save_path: Path = Path()

    @property
    def progress(self) -> float:
        if self.chunk_count == 0:
            return 0.0
        return self.chunks_received / self.chunk_count


class FileListener:
    """Threaded TCP server that receives files from a sender."""

    def __init__(
        self,
        config: ReceiverConfig,
        on_file_received: Optional[Callable[[Path, str], None]] = None,
        on_progress: Optional[Callable[[ReceivedFileInfo], None]] = None,
    ) -> None:
        self.config = config
        self._on_file_received = on_file_received
        self._on_progress = on_progress
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._encryption = EncryptionContext(enabled=config.encryption_enabled)
        self._receive_dir = Path(config.receive_directory)
        self._receive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the listener in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._serve_forever, daemon=True, name="file-listener"
        )
        self._thread.start()
        logger.info(
            "Listener started on %s:%d",
            self.config.listen_host,
            self.config.listen_port,
        )

    def stop(self) -> None:
        """Shut down the listener."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Listener stopped")

    # ------------------------------------------------------------------
    # Server loop
    # ------------------------------------------------------------------

    def _serve_forever(self) -> None:
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.config.listen_host, self.config.listen_port))
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)  # allow periodic check of _running

        while self._running:
            try:
                conn, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            logger.info("Connection from %s", addr)
            handler = threading.Thread(
                target=self._handle_connection,
                args=(conn, addr),
                daemon=True,
                name=f"conn-{addr}",
            )
            handler.start()

    # ------------------------------------------------------------------
    # Connection handler
    # ------------------------------------------------------------------

    def _handle_connection(self, conn: socket.socket, addr: tuple) -> None:
        file_info = ReceivedFileInfo()
        file_handle = None

        try:
            while True:
                header_data = self._recv_exact(conn, HEADER_SIZE)
                hdr = parse_header(header_data)
                if hdr is None:
                    logger.warning("Invalid header from %s", addr)
                    break

                payload = self._recv_exact(conn, hdr.payload_length)

                if not hdr.validate_payload(payload):
                    logger.warning("Payload integrity check failed from %s", addr)
                    self._send_error(conn, 1, "Integrity check failed")
                    break

                # --- Dispatch by message type ---

                if hdr.message_type == MSG_HANDSHAKE:
                    hs = parse_handshake_payload(payload)
                    logger.info("Handshake from sender=%s encryption=%s", hs.get("sender_id"), hs.get("encryption"))
                    self._send_ack(conn, True, "Ready")

                elif hdr.message_type == MSG_FILE_META:
                    meta = parse_file_meta_payload(payload)
                    file_info.filename = meta["filename"]
                    file_info.file_size = meta["file_size"]
                    file_info.mime_type = meta["mime_type"]
                    file_info.chunk_count = meta["chunk_count"]
                    file_info.chunk_size = meta["chunk_size"]
                    file_info.save_path = self._unique_path(file_info.filename)

                    logger.info(
                        "Receiving %s (%d bytes, %d chunks)",
                        file_info.filename,
                        file_info.file_size,
                        file_info.chunk_count,
                    )

                    file_handle = open(file_info.save_path, "wb")
                    self._send_ack(conn, True, "Metadata accepted")

                elif hdr.message_type == MSG_CHUNK:
                    chunk_idx, chunk_data = parse_chunk_payload(payload)
                    decrypted = self._encryption.decrypt(chunk_data)

                    if file_handle is None:
                        self._send_error(conn, 2, "No file metadata received")
                        break

                    file_handle.write(decrypted)
                    file_info.chunks_received += 1

                    if self._on_progress:
                        self._on_progress(file_info)

                    self._send_ack(conn, True, f"Chunk {chunk_idx} OK")

                elif hdr.message_type == MSG_DONE:
                    if file_handle:
                        file_handle.close()
                        file_handle = None
                    logger.info("Transfer complete: %s", file_info.save_path)
                    self._send_ack(conn, True, "File saved")

                    if self._on_file_received:
                        self._on_file_received(file_info.save_path, file_info.mime_type)
                    break

                else:
                    logger.warning("Unknown message type %d from %s", hdr.message_type, addr)
                    break

        except ConnectionError as exc:
            logger.error("Connection error from %s: %s", addr, exc)
        except Exception as exc:
            logger.error("Error handling connection from %s: %s", addr, exc)
        finally:
            if file_handle:
                file_handle.close()
            try:
                conn.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send_ack(self, conn: socket.socket, success: bool, message: str) -> None:
        payload = build_ack_payload(success, message)
        header = build_header(MSG_ACK, payload)
        conn.sendall(header + payload)

    def _send_error(self, conn: socket.socket, code: int, reason: str) -> None:
        payload = build_error_payload(code, reason)
        header = build_header(MSG_ERROR, payload)
        conn.sendall(header + payload)

    def _unique_path(self, filename: str) -> Path:
        """Return a path in the receive directory, appending a suffix if needed."""
        target = self._receive_dir / filename
        if not target.exists():
            return target
        stem = target.stem
        suffix = target.suffix
        counter = 1
        while target.exists():
            target = self._receive_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        return target

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
