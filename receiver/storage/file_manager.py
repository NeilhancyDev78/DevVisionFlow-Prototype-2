"""File storage manager for the receiver.

Handles saving received files, deduplication, and organising by date.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class FileManager:
    """Manages the receive directory and provides listing utilities."""

    def __init__(self, receive_directory: str) -> None:
        self._base_dir = Path(receive_directory)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def list_received(self) -> List[Path]:
        """Return a sorted list of all received files."""
        try:
            return sorted(
                p for p in self._base_dir.iterdir() if p.is_file()
            )
        except OSError as exc:
            logger.error("Failed to list received files: %s", exc)
            return []

    def get_dated_subdir(self) -> Path:
        """Return (and create) a subdirectory named by today's date."""
        today = datetime.now().strftime("%Y-%m-%d")
        subdir = self._base_dir / today
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir

    def cleanup_old(self, max_age_days: int = 30) -> int:
        """Delete received files older than *max_age_days*. Returns count."""
        import time

        now = time.time()
        cutoff = now - (max_age_days * 86400)
        removed = 0

        for path in self._base_dir.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning("Could not remove %s: %s", path, exc)

        logger.info("Cleaned up %d old files", removed)
        return removed
