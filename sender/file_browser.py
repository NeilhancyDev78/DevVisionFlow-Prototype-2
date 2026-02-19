"""File browser component for the sender.

Lists files in a configurable directory and supports navigation via swipe
gestures and selection via pinch.
"""

import logging
import mimetypes
import os
from pathlib import Path
from typing import List, Optional

from sender.config import SenderConfig

logger = logging.getLogger(__name__)


class FileEntry:
    """Lightweight representation of a file in the send directory."""

    __slots__ = ("name", "path", "size", "mime_type")

    def __init__(self, filepath: Path) -> None:
        self.path: Path = filepath
        self.name: str = filepath.name
        self.size: int = filepath.stat().st_size if filepath.exists() else 0
        self.mime_type: str = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"

    @property
    def size_human(self) -> str:
        """Return a human-readable file size string."""
        size = self.size
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def __repr__(self) -> str:
        return f"FileEntry({self.name!r}, {self.size_human})"


class FileBrowser:
    """Provides a navigable list of files from the send directory."""

    def __init__(self, config: SenderConfig) -> None:
        self.config = config
        self._directory: Path = Path(config.send_directory)
        self._files: List[FileEntry] = []
        self._current_index: int = 0

        # Ensure the send directory exists
        self._directory.mkdir(parents=True, exist_ok=True)
        self.refresh()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def files(self) -> List[FileEntry]:
        return self._files

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_file(self) -> Optional[FileEntry]:
        """Return the currently highlighted file, or None if empty."""
        if not self._files:
            return None
        return self._files[self._current_index]

    @property
    def is_empty(self) -> bool:
        return len(self._files) == 0

    @property
    def file_count(self) -> int:
        return len(self._files)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def next_file(self) -> Optional[FileEntry]:
        """Move to the next file (wrap-around)."""
        if not self._files:
            return None
        self._current_index = (self._current_index + 1) % len(self._files)
        return self.current_file

    def previous_file(self) -> Optional[FileEntry]:
        """Move to the previous file (wrap-around)."""
        if not self._files:
            return None
        self._current_index = (self._current_index - 1) % len(self._files)
        return self.current_file

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-scan the send directory for files."""
        try:
            entries = sorted(self._directory.iterdir())
            self._files = [
                FileEntry(e) for e in entries if e.is_file()
            ]
        except OSError as exc:
            logger.error("Failed to scan directory %s: %s", self._directory, exc)
            self._files = []

        # Clamp the index
        if self._files:
            self._current_index = min(self._current_index, len(self._files) - 1)
        else:
            self._current_index = 0

        logger.debug("File browser refreshed: %d files found", len(self._files))

    def get_visible_window(self, window_size: int = 7) -> List[FileEntry]:
        """Return a window of files centred on the current index.

        Useful for rendering a scrollable list on-screen without showing
        every file at once.
        """
        if not self._files:
            return []

        half = window_size // 2
        total = len(self._files)

        if total <= window_size:
            return list(self._files)

        start = self._current_index - half
        indices = [(start + i) % total for i in range(window_size)]
        return [self._files[i] for i in indices]
