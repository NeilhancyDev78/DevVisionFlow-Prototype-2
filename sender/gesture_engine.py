"""Gesture detection state machine for the file transfer sender.

Implements a 6-state FSM (IDLE -> BROWSING -> FILE_SELECTED ->
CONFIRMING_SEND -> SENDING -> SEND_COMPLETE) driven by hand gestures
recognised through MediaPipe landmark analysis, the ported keypoint
classifier, and the point-history classifier from Prototype 1.
"""

import logging
import time
from collections import deque
from typing import List, Optional, Tuple

import numpy as np

from shared.constants import (
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_SWIPE_LEFT,
    GESTURE_SWIPE_RIGHT,
    GESTURE_TWO_FINGER,
    KEYPOINT_CLOSE,
    KEYPOINT_OPEN,
    KEYPOINT_POINTER,
    STATE_BROWSING,
    STATE_CONFIRMING_SEND,
    STATE_FILE_SELECTED,
    STATE_IDLE,
    STATE_SEND_COMPLETE,
    STATE_SENDING,
    SEND_COMPLETE_RESET_DELAY,
)
from sender.config import SenderConfig

logger = logging.getLogger(__name__)

# Valid gestures for each state
_VALID_GESTURES: dict = {
    STATE_IDLE: {GESTURE_OPEN_PALM},
    STATE_BROWSING: {GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT, GESTURE_PINCH, GESTURE_FIST},
    STATE_FILE_SELECTED: {
        GESTURE_OPEN_PALM,
        GESTURE_SWIPE_LEFT,
        GESTURE_SWIPE_RIGHT,
        GESTURE_FIST,
        GESTURE_TWO_FINGER,
    },
    STATE_CONFIRMING_SEND: {GESTURE_PINCH, GESTURE_FIST},
    STATE_SENDING: {GESTURE_FIST},  # Only cancel allowed while sending
    STATE_SEND_COMPLETE: set(),  # Auto-reset, no gestures needed
}


class GestureEngine:
    """Combines gesture classification with a state machine for file transfer."""

    def __init__(self, config: SenderConfig) -> None:
        self.config = config
        self._state: str = STATE_IDLE

        # Per-gesture cooldown timestamps
        self._cooldowns: dict = {
            GESTURE_OPEN_PALM: 0.0,
            GESTURE_SWIPE_LEFT: 0.0,
            GESTURE_SWIPE_RIGHT: 0.0,
            GESTURE_PINCH: 0.0,
            GESTURE_FIST: 0.0,
            GESTURE_TWO_FINGER: 0.0,
        }
        self._cooldown_durations: dict = {
            GESTURE_OPEN_PALM: config.cooldown_open_palm,
            GESTURE_SWIPE_LEFT: config.cooldown_swipe,
            GESTURE_SWIPE_RIGHT: config.cooldown_swipe,
            GESTURE_PINCH: config.cooldown_pinch,
            GESTURE_FIST: config.cooldown_fist,
            GESTURE_TWO_FINGER: config.cooldown_two_finger,
        }

        # Hysteresis buffer: track consecutive detections per gesture
        self._hysteresis: dict = {g: 0 for g in self._cooldowns}
        self._hysteresis_threshold: int = config.hysteresis_frames

        # Point history for swipe detection
        self._point_history: deque = deque(maxlen=16)

        # Timestamp for auto-reset from SEND_COMPLETE
        self._send_complete_time: float = 0.0

        # Last detected gesture (for UI display)
        self.last_gesture: str = GESTURE_NONE
        # Callback: set externally to receive confirmed gestures
        self.on_gesture_confirmed: Optional[callable] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        """Return the current state machine state."""
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        if value != self._state:
            logger.info("State transition: %s -> %s", self._state, value)
            self._state = value

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def update(self, landmarks: List[Tuple[int, int]]) -> Optional[str]:
        """Process a frame's landmarks and return a confirmed gesture or None.

        This is the main entry point called once per frame from the main loop.
        """
        now = time.time()

        # Handle auto-reset from SEND_COMPLETE
        if self._state == STATE_SEND_COMPLETE:
            if now - self._send_complete_time >= SEND_COMPLETE_RESET_DELAY:
                self.state = STATE_IDLE
            return None

        if not landmarks or len(landmarks) < 21:
            self._reset_hysteresis()
            self.last_gesture = GESTURE_NONE
            return None

        # Update point history for swipe detection
        index_tip = landmarks[8]
        self._point_history.append(index_tip)

        # Classify the current gesture from landmarks
        raw_gesture = self._classify_gesture(landmarks)

        # Apply hysteresis
        confirmed = self._apply_hysteresis(raw_gesture, now)

        if confirmed and confirmed != GESTURE_NONE:
            self.last_gesture = confirmed
            self._process_transition(confirmed)
            if self.on_gesture_confirmed:
                self.on_gesture_confirmed(confirmed)
            return confirmed

        return None

    # ------------------------------------------------------------------
    # Gesture classification
    # ------------------------------------------------------------------

    def _classify_gesture(self, landmarks: List[Tuple[int, int]]) -> str:
        """Determine the gesture from raw landmark positions.

        Uses geometric heuristics similar to how Prototype 1 maps
        landmark distances to gesture labels.
        """
        # Finger tip and base landmarks (MediaPipe hand indices)
        thumb_tip = np.array(landmarks[4])
        index_tip = np.array(landmarks[8])
        middle_tip = np.array(landmarks[12])
        ring_tip = np.array(landmarks[16])
        pinky_tip = np.array(landmarks[20])

        thumb_ip = np.array(landmarks[3])
        index_pip = np.array(landmarks[6])
        middle_pip = np.array(landmarks[10])
        ring_pip = np.array(landmarks[14])
        pinky_pip = np.array(landmarks[18])

        wrist = np.array(landmarks[0])

        # Finger extension checks (tip further from wrist than PIP)
        def is_extended(tip: np.ndarray, pip: np.ndarray) -> bool:
            return float(np.linalg.norm(tip - wrist)) > float(
                np.linalg.norm(pip - wrist)
            )

        thumb_ext = is_extended(thumb_tip, thumb_ip)
        index_ext = is_extended(index_tip, index_pip)
        middle_ext = is_extended(middle_tip, middle_pip)
        ring_ext = is_extended(ring_tip, ring_pip)
        pinky_ext = is_extended(pinky_tip, pinky_pip)

        extended_count = sum([thumb_ext, index_ext, middle_ext, ring_ext, pinky_ext])

        # Pinch: thumb tip very close to index tip
        pinch_dist = float(np.linalg.norm(thumb_tip - index_tip))
        if pinch_dist < 40:
            return GESTURE_PINCH

        # Open palm: all 5 fingers extended
        if extended_count == 5:
            return GESTURE_OPEN_PALM

        # Fist: no fingers extended
        if extended_count == 0:
            return GESTURE_FIST

        # Two-finger point: index + middle extended, others curled
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return GESTURE_TWO_FINGER

        # Swipe detection via point history
        swipe = self._detect_swipe()
        if swipe:
            return swipe

        return GESTURE_NONE

    def _detect_swipe(self) -> Optional[str]:
        """Detect a horizontal swipe from the point history buffer."""
        if len(self._point_history) < 8:
            return None

        history = list(self._point_history)
        start_x = history[0][0]
        end_x = history[-1][0]
        dx = end_x - start_x

        # Require a minimum horizontal displacement
        if abs(dx) < 80:
            return None

        # Check that vertical displacement is small (horizontal swipe)
        start_y = history[0][1]
        end_y = history[-1][1]
        dy = abs(end_y - start_y)
        if dy > abs(dx) * 0.6:
            return None

        if dx < -80:
            return GESTURE_SWIPE_LEFT
        if dx > 80:
            return GESTURE_SWIPE_RIGHT

        return None

    # ------------------------------------------------------------------
    # Hysteresis and cooldown
    # ------------------------------------------------------------------

    def _apply_hysteresis(self, gesture: str, now: float) -> Optional[str]:
        """Apply consecutive-frame hysteresis and per-gesture cooldown."""
        if gesture == GESTURE_NONE:
            self._reset_hysteresis()
            return None

        # Only process gestures valid in the current state
        if gesture not in _VALID_GESTURES.get(self._state, set()):
            self._reset_hysteresis()
            return None

        # Increment count for this gesture, reset others
        for g in self._hysteresis:
            if g == gesture:
                self._hysteresis[g] += 1
            else:
                self._hysteresis[g] = 0

        # Check hysteresis threshold
        if self._hysteresis[gesture] < self._hysteresis_threshold:
            return None

        # Check cooldown
        cooldown = self._cooldown_durations.get(gesture, 0.5)
        if now - self._cooldowns.get(gesture, 0.0) < cooldown:
            return None

        # Gesture confirmed -- update cooldown and reset hysteresis
        self._cooldowns[gesture] = now
        self._reset_hysteresis()
        self._point_history.clear()
        return gesture

    def _reset_hysteresis(self) -> None:
        for g in self._hysteresis:
            self._hysteresis[g] = 0

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _process_transition(self, gesture: str) -> None:
        """Advance the state machine based on the confirmed gesture."""
        if self._state == STATE_IDLE:
            if gesture == GESTURE_OPEN_PALM:
                self.state = STATE_BROWSING

        elif self._state == STATE_BROWSING:
            if gesture == GESTURE_PINCH:
                self.state = STATE_FILE_SELECTED
            elif gesture == GESTURE_FIST:
                self.state = STATE_IDLE
            # Swipe left/right stay in BROWSING (navigation handled externally)

        elif self._state == STATE_FILE_SELECTED:
            if gesture == GESTURE_OPEN_PALM:
                self.state = STATE_CONFIRMING_SEND
            elif gesture in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT):
                self.state = STATE_BROWSING
            elif gesture == GESTURE_FIST:
                self.state = STATE_IDLE

        elif self._state == STATE_CONFIRMING_SEND:
            if gesture == GESTURE_PINCH:
                self.state = STATE_SENDING
            elif gesture == GESTURE_FIST:
                self.state = STATE_FILE_SELECTED

        elif self._state == STATE_SENDING:
            if gesture == GESTURE_FIST:
                # Cancel transfer -- revert to FILE_SELECTED
                self.state = STATE_FILE_SELECTED

    # ------------------------------------------------------------------
    # External triggers
    # ------------------------------------------------------------------

    def notify_transfer_complete(self) -> None:
        """Called by the network layer when a transfer finishes."""
        self.state = STATE_SEND_COMPLETE
        self._send_complete_time = time.time()

    def notify_transfer_error(self) -> None:
        """Called by the network layer on transfer failure."""
        self.state = STATE_FILE_SELECTED
