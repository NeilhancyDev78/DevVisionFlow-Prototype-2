"""Receiver entry point for the Air Gesture-Controlled File Transfer System.

Starts a TCP listener that accepts incoming file transfers, saves them,
and optionally previews them based on MIME type.
"""

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from receiver.config import ReceiverConfig
from receiver.effects.sound import SoundManager
from receiver.network.listener import FileListener, ReceivedFileInfo
from receiver.preview.file_preview import preview_file
from receiver.storage.file_manager import FileManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class ReceiverApp:
    """Top-level application that wires together all receiver components."""

    def __init__(self, config: Optional[ReceiverConfig] = None) -> None:
        self.config = config or ReceiverConfig()
        self.file_manager = FileManager(self.config.receive_directory)
        self.sound = SoundManager(
            enabled=self.config.sound_enabled,
            volume=self.config.sound_volume,
        )
        self.listener = FileListener(
            config=self.config,
            on_file_received=self._on_file_received,
            on_progress=self._on_progress,
        )
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the receiver and block until interrupted."""
        self._running = True

        # Graceful shutdown on SIGINT / SIGTERM
        def _handle_signal(signum: int, frame: object) -> None:
            logger.info("Signal %d received -- shutting down", signum)
            self._running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        self.listener.start()
        logger.info(
            "Receiver listening on %s:%d -- files will be saved to %s",
            self.config.listen_host,
            self.config.listen_port,
            self.config.receive_directory,
        )

        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_file_received(self, filepath: Path, mime_type: str) -> None:
        """Called when a complete file has been received and saved."""
        logger.info("File received: %s (%s)", filepath.name, mime_type)
        self.sound.play("complete")

        if self.config.auto_preview:
            preview_file(filepath, mime_type)

    def _on_progress(self, info: ReceivedFileInfo) -> None:
        """Called after each chunk is received."""
        if info.chunks_received == 1:
            self.sound.play("incoming")
            logger.info(
                "Incoming file: %s (%d bytes)", info.filename, info.file_size
            )

        if info.chunk_count > 0:
            pct = int(info.progress * 100)
            logger.debug(
                "Progress: %s %d/%d chunks (%d%%)",
                info.filename,
                info.chunks_received,
                info.chunk_count,
                pct,
            )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        logger.info("Shutting down receiver")
        self.listener.stop()
        self.sound.shutdown()


def main() -> None:
    config = ReceiverConfig()
    app = ReceiverApp(config)
    app.run()


if __name__ == "__main__":
    main()
