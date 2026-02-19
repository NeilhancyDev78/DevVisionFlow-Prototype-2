"""Auto-preview engine that dispatches by MIME type.

Supports images (via OpenCV), text files (via OpenCV overlay), and
provides a fallback that logs the file path for the user to open
manually.
"""

import logging
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# MIME prefixes we can handle natively
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/bmp"}
_TEXT_TYPES = {
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
    "text/html",
}


def preview_file(filepath: Path, mime_type: str) -> None:
    """Open a preview window appropriate for the file type.

    Args:
        filepath: Path to the received file on disk.
        mime_type: MIME type string (e.g. ``"image/png"``).
    """
    if mime_type in _IMAGE_TYPES:
        _preview_image(filepath)
    elif mime_type in _TEXT_TYPES or mime_type.startswith("text/"):
        _preview_text(filepath)
    else:
        _preview_fallback(filepath, mime_type)


def _preview_image(filepath: Path) -> None:
    """Display an image in an OpenCV window."""
    img = cv2.imread(str(filepath))
    if img is None:
        logger.warning("Could not read image: %s", filepath)
        return

    window_name = f"Preview: {filepath.name}"
    cv2.imshow(window_name, img)
    logger.info("Showing image preview -- press any key to close")
    cv2.waitKey(0)
    cv2.destroyWindow(window_name)


def _preview_text(filepath: Path, max_lines: int = 30) -> None:
    """Display a text file as an OpenCV overlay image."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Could not read text file %s: %s", filepath, exc)
        return

    lines = text.splitlines()[:max_lines]
    if len(lines) == 0:
        lines = ["(empty file)"]

    # Build a simple image with the text rendered
    line_height = 20
    margin = 15
    width = 700
    height = margin * 2 + line_height * len(lines)
    img = np.zeros((height, width, 3), dtype=np.uint8)

    for i, line in enumerate(lines):
        display = line[:100]  # cap long lines
        y = margin + (i + 1) * line_height
        cv2.putText(
            img,
            display,
            (margin, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (220, 220, 220),
            1,
        )

    window_name = f"Preview: {filepath.name}"
    cv2.imshow(window_name, img)
    logger.info("Showing text preview -- press any key to close")
    cv2.waitKey(0)
    cv2.destroyWindow(window_name)


def _preview_fallback(filepath: Path, mime_type: str) -> None:
    """Log the path and attempt to open with the system default handler."""
    logger.info(
        "No built-in preview for %s (%s) -- attempting system open",
        filepath.name,
        mime_type,
    )
    try:
        if sys.platform == "linux":
            subprocess.Popen(["xdg-open", str(filepath)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(filepath)])
        elif sys.platform == "win32":
            import os
            os.startfile(str(filepath))  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Could not open file with system handler: %s", exc)
        logger.info("File saved at: %s", filepath)
