"""Integration test: file transfer between sender and receiver on localhost.

Spins up a receiver listener, sends a file from the transmitter, and
verifies the file arrives intact.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from receiver.config import ReceiverConfig
from receiver.network.listener import FileListener
from sender.config import SenderConfig
from sender.network.transmitter import FileTransmitter


class TestLocalhostTransfer(unittest.TestCase):
    """End-to-end transfer test over localhost."""

    def setUp(self) -> None:
        self._send_dir = tempfile.mkdtemp()
        self._recv_dir = tempfile.mkdtemp()

        # Create a test file
        self._test_file = Path(self._send_dir) / "transfer_test.txt"
        self._test_content = b"Hello from DevVisionFlow Prototype 2!\n" * 100
        self._test_file.write_bytes(self._test_content)

        self._received_path: Path = Path()
        self._received_mime: str = ""

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._send_dir, ignore_errors=True)
        shutil.rmtree(self._recv_dir, ignore_errors=True)

    def _on_received(self, filepath: Path, mime_type: str) -> None:
        self._received_path = filepath
        self._received_mime = mime_type

    def test_transfer_small_file(self) -> None:
        """Send a small file and verify it arrives intact."""
        # Set up receiver
        recv_config = ReceiverConfig()
        recv_config.listen_host = "127.0.0.1"
        recv_config.listen_port = 19876  # Use a non-default port for tests
        recv_config.receive_directory = self._recv_dir
        recv_config.auto_preview = False

        listener = FileListener(
            config=recv_config,
            on_file_received=self._on_received,
        )
        listener.start()
        time.sleep(0.3)  # give listener time to bind

        try:
            # Set up sender
            send_config = SenderConfig()
            send_config.receiver_host = "127.0.0.1"
            send_config.receiver_port = 19876
            send_config.encryption_enabled = False

            transmitter = FileTransmitter(send_config)
            transmitter.start_transfer(self._test_file)

            # Wait for transfer to complete (with timeout)
            deadline = time.time() + 10
            while transmitter.is_transferring and time.time() < deadline:
                time.sleep(0.1)

            # Check progress
            progress = transmitter.get_latest_progress()
            self.assertIsNotNone(progress)
            if progress:
                self.assertTrue(progress.done, f"Transfer not done. Error: {progress.error}")

            # Give a moment for the file to be written
            time.sleep(0.5)

            # Verify received file
            self.assertTrue(self._received_path.exists(), "Received file does not exist")
            received_content = self._received_path.read_bytes()
            self.assertEqual(received_content, self._test_content)
            self.assertIn("text", self._received_mime)

        finally:
            listener.stop()


if __name__ == "__main__":
    unittest.main()
