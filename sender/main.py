"""Sender entry point for the Air Gesture-Controlled File Transfer System.

Main loop: capture webcam frames, detect gestures, render UI overlays,
and dispatch file transfers to the background thread.
"""

import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from sender.config import SenderConfig
from sender.effects.sound import SoundManager
from sender.file_browser import FileBrowser
from sender.gesture_engine import GestureEngine
from sender.hand_detector import HandDetector
from sender.network.transmitter import FileTransmitter
from sender.ui_renderer import UIRenderer
from sender.utils.fps_calc import CvFpsCalc
from shared.constants import (
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_SWIPE_LEFT,
    GESTURE_SWIPE_RIGHT,
    GESTURE_TWO_FINGER,
    STATE_BROWSING,
    STATE_CONFIRMING_SEND,
    STATE_FILE_SELECTED,
    STATE_IDLE,
    STATE_SEND_COMPLETE,
    STATE_SENDING,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class SenderApp:
    """Top-level application that wires together all sender components."""

    def __init__(self, config: Optional[SenderConfig] = None) -> None:
        self.config = config or SenderConfig()

        # Components
        self.hand_detector = HandDetector(self.config)
        self.gesture_engine = GestureEngine(self.config)
        self.file_browser = FileBrowser(self.config)
        self.transmitter = FileTransmitter(self.config)
        self.ui = UIRenderer(self.config)
        self.fps_calc = CvFpsCalc(buffer_len=10)
        self.sound = SoundManager(
            enabled=self.config.sound_enabled,
            volume=self.config.sound_volume,
        )

        # Network connection status for UI indicator
        self._connection_status: str = "disconnected"

        # Wire gesture callbacks
        self.gesture_engine.on_gesture_confirmed = self._on_gesture

        # Camera
        self._cap: Optional[cv2.VideoCapture] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the main capture-and-render loop."""
        self._cap = cv2.VideoCapture(0)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)

        if not self._cap.isOpened():
            logger.error("Cannot open webcam")
            return

        logger.info("Sender started -- press 'q' to quit")

        try:
            while True:
                ok, frame = self._cap.read()
                if not ok:
                    logger.warning("Frame capture failed")
                    break

                frame = cv2.flip(frame, 1)  # mirror
                frame, landmarks = self.hand_detector.find_hands(frame)

                # Gesture processing
                gesture = self.gesture_engine.update(landmarks)

                # Poll transfer progress
                self._poll_transfer()

                # --- Render overlays ---
                state = self.gesture_engine.state
                fps = self.fps_calc.get()

                frame = self.ui.draw_state_badge(frame, state)
                if self.config.show_fps:
                    frame = self.ui.draw_fps(frame, fps)
                frame = self.ui.draw_connection_indicator(frame, self._connection_status)

                # Hand glow
                hand_center = self._hand_center(landmarks)
                frame = self.ui.draw_gesture_glow(
                    frame, self.gesture_engine.last_gesture, hand_center
                )
                frame = self.ui.draw_gesture_label(frame, self.gesture_engine.last_gesture)

                if not landmarks:
                    frame = self.ui.draw_no_hand(frame)

                # State-specific rendering
                if state in (STATE_BROWSING, STATE_FILE_SELECTED):
                    self.file_browser.refresh()  # re-scan for changes
                    visible = self.file_browser.get_visible_window()
                    frame = self.ui.draw_file_browser(
                        frame,
                        visible,
                        self.file_browser.current_index,
                        self.file_browser.file_count,
                        selected=(state == STATE_FILE_SELECTED),
                    )
                elif state == STATE_CONFIRMING_SEND:
                    frame = self.ui.draw_confirmation_prompt(frame)
                elif state == STATE_SENDING:
                    progress = self.transmitter.get_latest_progress()
                    frac = progress.fraction if progress else 0.0
                    frame = self.ui.draw_progress_arc(frame, frac)
                elif state == STATE_SEND_COMPLETE:
                    frame = self.ui.draw_send_complete(frame)

                cv2.imshow("DevVisionFlow Sender", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self._shutdown()

    # ------------------------------------------------------------------
    # Gesture callback
    # ------------------------------------------------------------------

    def _on_gesture(self, gesture: str) -> None:
        """Called when a gesture is confirmed by the engine."""
        self.sound.play("gesture")

        if gesture == GESTURE_SWIPE_RIGHT:
            self.file_browser.next_file()
        elif gesture == GESTURE_SWIPE_LEFT:
            self.file_browser.previous_file()
        elif gesture == GESTURE_PINCH:
            if self.gesture_engine.state == STATE_SENDING:
                # Pinch in CONFIRMING -> SENDING triggers transfer
                self._start_transfer()
        elif gesture == GESTURE_FIST:
            if self.transmitter.is_transferring:
                self.transmitter.cancel()

        # Sound cues for specific transitions
        if gesture == GESTURE_PINCH and self.gesture_engine.state == STATE_FILE_SELECTED:
            self.sound.play("select")
        elif gesture == GESTURE_OPEN_PALM and self.gesture_engine.state == STATE_CONFIRMING_SEND:
            self.sound.play("send")

    # ------------------------------------------------------------------
    # Transfer management
    # ------------------------------------------------------------------

    def _start_transfer(self) -> None:
        """Kick off the file transfer in the background thread."""
        current = self.file_browser.current_file
        if current is None:
            logger.warning("No file selected for transfer")
            self.gesture_engine.notify_transfer_error()
            return
        logger.info("Starting transfer of %s", current.name)
        self._connection_status = "connecting"
        self.sound.play("send")
        self.transmitter.start_transfer(current.path)

    def _poll_transfer(self) -> None:
        """Check transfer progress and update state accordingly."""
        if not self.transmitter.is_transferring and self.gesture_engine.state != STATE_SENDING:
            return

        progress = self.transmitter.get_latest_progress()
        if progress is None:
            return

        if progress.error:
            logger.error("Transfer error: %s", progress.error)
            self._connection_status = "disconnected"
            self.gesture_engine.notify_transfer_error()
            self.sound.play("error")
        elif progress.done:
            self._connection_status = "connected"
            self.gesture_engine.notify_transfer_complete()
            self.sound.play("complete")
        else:
            self._connection_status = "connected"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hand_center(landmarks: list) -> Optional[Tuple[int, int]]:
        """Compute the centroid of all landmarks."""
        if not landmarks:
            return None
        xs = [p[0] for p in landmarks]
        ys = [p[1] for p in landmarks]
        return (int(np.mean(xs)), int(np.mean(ys)))

    def _shutdown(self) -> None:
        """Release all resources."""
        logger.info("Shutting down sender")
        self.transmitter.cancel()
        self.hand_detector.release()
        self.sound.shutdown()
        if self._cap:
            self._cap.release()
        cv2.destroyAllWindows()


def main() -> None:
    config = SenderConfig()
    app = SenderApp(config)
    app.run()


if __name__ == "__main__":
    main()
