"""OpenCV overlay renderer for the sender UI.

Draws the file browser list, state badge, gesture glow, progress arc,
and connection indicator on top of the webcam feed.
"""

import math
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from sender.config import SenderConfig
from sender.file_browser import FileEntry
from shared.constants import (
    COLOR_BROWSING,
    COLOR_COMPLETE,
    COLOR_CONNECTED,
    COLOR_CONNECTING,
    COLOR_DISCONNECTED,
    COLOR_ERROR,
    COLOR_HIGHLIGHT,
    COLOR_IDLE,
    COLOR_SENDING,
    COLOR_TEXT,
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_SWIPE_LEFT,
    GESTURE_SWIPE_RIGHT,
    GESTURE_TWO_FINGER,
    STATE_BROWSING,
    STATE_COLORS,
    STATE_CONFIRMING_SEND,
    STATE_FILE_SELECTED,
    STATE_IDLE,
    STATE_SEND_COMPLETE,
    STATE_SENDING,
)

# Gesture -> glow colour mapping (BGR)
_GESTURE_COLORS: dict = {
    GESTURE_OPEN_PALM: (0, 255, 128),
    GESTURE_SWIPE_LEFT: (255, 200, 0),
    GESTURE_SWIPE_RIGHT: (255, 200, 0),
    GESTURE_PINCH: (0, 200, 255),
    GESTURE_FIST: (0, 0, 255),
    GESTURE_TWO_FINGER: (255, 0, 200),
    GESTURE_NONE: (128, 128, 128),
}


class UIRenderer:
    """Renders all on-screen overlays onto the webcam frame."""

    def __init__(self, config: SenderConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public draw methods
    # ------------------------------------------------------------------

    def draw_state_badge(self, img: np.ndarray, state: str) -> np.ndarray:
        """Draw a small coloured pill showing the current state."""
        color = STATE_COLORS.get(state, COLOR_IDLE)
        label = state.replace("_", " ")
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        x, y = 10, 25
        cv2.rectangle(img, (x, y - th - 6), (x + tw + 16, y + 6), color, -1)
        cv2.putText(img, label, (x + 8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        return img

    def draw_gesture_glow(
        self,
        img: np.ndarray,
        gesture: str,
        hand_center: Optional[Tuple[int, int]],
    ) -> np.ndarray:
        """Draw a semi-transparent glow circle around the hand."""
        if gesture == GESTURE_NONE or hand_center is None:
            return img
        color = _GESTURE_COLORS.get(gesture, (128, 128, 128))
        overlay = img.copy()
        cv2.circle(overlay, hand_center, 60, color, -1)
        cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)
        return img

    def draw_file_browser(
        self,
        img: np.ndarray,
        visible_files: List[FileEntry],
        current_index: int,
        total_files: int,
        selected: bool = False,
    ) -> np.ndarray:
        """Draw the file list overlay on the left side of the frame."""
        if not visible_files:
            cv2.putText(
                img,
                "No files found",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                COLOR_ERROR,
                2,
            )
            return img

        x_start = 10
        y_start = 60
        row_height = 32
        max_name_len = 28

        # Semi-transparent background
        overlay = img.copy()
        panel_h = len(visible_files) * row_height + 20
        cv2.rectangle(overlay, (x_start, y_start - 10), (320, y_start + panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

        for i, entry in enumerate(visible_files):
            y = y_start + i * row_height + 20
            name = entry.name
            if len(name) > max_name_len:
                name = name[: max_name_len - 3] + "..."

            is_current = (entry == visible_files[len(visible_files) // 2]) if len(visible_files) > 1 else True

            if is_current:
                # Highlight current file
                highlight_color = COLOR_HIGHLIGHT if not selected else (0, 255, 0)
                cv2.rectangle(
                    img,
                    (x_start + 2, y - 16),
                    (315, y + 6),
                    highlight_color,
                    2 if not selected else -1,
                )
                if selected:
                    # Selection pulse effect (sinusoidal alpha)
                    alpha = 0.3 + 0.2 * math.sin(time.time() * 6)
                    pulse_overlay = img.copy()
                    cv2.rectangle(pulse_overlay, (x_start + 2, y - 16), (315, y + 6), highlight_color, -1)
                    cv2.addWeighted(pulse_overlay, alpha, img, 1 - alpha, 0, img)

                text_color = (255, 255, 255)
            else:
                text_color = (180, 180, 180)

            cv2.putText(img, name, (x_start + 8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1)
            # Size on the right
            size_str = entry.size_human
            cv2.putText(img, size_str, (230, y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)

        # File counter
        cv2.putText(
            img,
            f"{current_index + 1}/{total_files}",
            (x_start + 8, y_start + panel_h + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            COLOR_TEXT,
            1,
        )
        return img

    def draw_progress_arc(
        self, img: np.ndarray, progress: float
    ) -> np.ndarray:
        """Draw a circular progress indicator (0.0 to 1.0)."""
        h, w = img.shape[:2]
        center = (w - 50, h - 50)
        radius = 30
        angle = int(progress * 360)

        # Background circle
        cv2.circle(img, center, radius, (60, 60, 60), 2)
        # Progress arc
        if angle > 0:
            cv2.ellipse(img, center, (radius, radius), -90, 0, angle, COLOR_SENDING, 3)
        # Percentage text
        pct = f"{int(progress * 100)}%"
        (tw, _), _ = cv2.getTextSize(pct, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.putText(
            img,
            pct,
            (center[0] - tw // 2, center[1] + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            COLOR_TEXT,
            1,
        )
        return img

    def draw_connection_indicator(
        self, img: np.ndarray, status: str
    ) -> np.ndarray:
        """Draw a small dot indicating network connection status.

        Args:
            status: One of ``"connected"``, ``"connecting"``, ``"disconnected"``.
        """
        color_map = {
            "connected": COLOR_CONNECTED,
            "connecting": COLOR_CONNECTING,
            "disconnected": COLOR_DISCONNECTED,
        }
        color = color_map.get(status, COLOR_DISCONNECTED)
        h, w = img.shape[:2]
        cv2.circle(img, (w - 15, 15), 6, color, -1)
        return img

    def draw_fps(self, img: np.ndarray, fps: float) -> np.ndarray:
        """Draw the FPS counter in the top-right area."""
        h, w = img.shape[:2]
        cv2.putText(
            img,
            f"FPS: {int(fps)}",
            (w - 110, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )
        return img

    def draw_gesture_label(self, img: np.ndarray, gesture: str) -> np.ndarray:
        """Show the name of the last recognised gesture."""
        if gesture == GESTURE_NONE:
            return img
        h, w = img.shape[:2]
        cv2.putText(
            img,
            f"Gesture: {gesture}",
            (10, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            _GESTURE_COLORS.get(gesture, COLOR_TEXT),
            1,
        )
        return img

    def draw_confirmation_prompt(self, img: np.ndarray) -> np.ndarray:
        """Draw a confirmation prompt in CONFIRMING_SEND state."""
        h, w = img.shape[:2]
        overlay = img.copy()
        cv2.rectangle(overlay, (w // 4, h // 3), (3 * w // 4, 2 * h // 3), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        cv2.putText(
            img,
            "Confirm send?",
            (w // 4 + 30, h // 2 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            COLOR_TEXT,
            2,
        )
        cv2.putText(
            img,
            "Pinch to send | Fist to cancel",
            (w // 4 + 10, h // 2 + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 180, 180),
            1,
        )
        return img

    def draw_send_complete(self, img: np.ndarray) -> np.ndarray:
        """Flash a success banner."""
        h, w = img.shape[:2]
        overlay = img.copy()
        cv2.rectangle(overlay, (0, h // 2 - 30), (w, h // 2 + 30), COLOR_COMPLETE, -1)
        cv2.addWeighted(overlay, 0.4, img, 0.6, 0, img)
        cv2.putText(
            img,
            "Transfer Complete!",
            (w // 4, h // 2 + 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            COLOR_TEXT,
            2,
        )
        return img

    def draw_no_hand(self, img: np.ndarray) -> np.ndarray:
        """Show a 'no hand detected' message."""
        h, w = img.shape[:2]
        cv2.putText(
            img,
            "No hand detected",
            (w // 2 - 90, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (100, 100, 100),
            1,
        )
        return img
