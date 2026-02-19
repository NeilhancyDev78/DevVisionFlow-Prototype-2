"""Tests for the gesture detection state machine."""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sender.config import SenderConfig
from sender.gesture_engine import GestureEngine
from shared.constants import (
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_SWIPE_LEFT,
    GESTURE_SWIPE_RIGHT,
    STATE_BROWSING,
    STATE_CONFIRMING_SEND,
    STATE_FILE_SELECTED,
    STATE_IDLE,
    STATE_SEND_COMPLETE,
    STATE_SENDING,
)


def _make_engine(hysteresis: int = 1, cooldown: float = 0.0) -> GestureEngine:
    """Create a GestureEngine with minimal hysteresis/cooldown for testing."""
    config = SenderConfig()
    config.hysteresis_frames = hysteresis
    config.cooldown_open_palm = cooldown
    config.cooldown_swipe = cooldown
    config.cooldown_pinch = cooldown
    config.cooldown_fist = cooldown
    config.cooldown_two_finger = cooldown
    return _engine_with_config(config)


def _engine_with_config(config: SenderConfig) -> GestureEngine:
    return GestureEngine(config)


class TestStateTransitions(unittest.TestCase):
    """Test that the state machine transitions are correct."""

    def test_initial_state_is_idle(self) -> None:
        engine = _make_engine()
        self.assertEqual(engine.state, STATE_IDLE)

    def test_idle_to_browsing_on_open_palm(self) -> None:
        engine = _make_engine()
        engine.state = STATE_IDLE
        engine._process_transition(GESTURE_OPEN_PALM)
        self.assertEqual(engine.state, STATE_BROWSING)

    def test_browsing_to_selected_on_pinch(self) -> None:
        engine = _make_engine()
        engine.state = STATE_BROWSING
        engine._process_transition(GESTURE_PINCH)
        self.assertEqual(engine.state, STATE_FILE_SELECTED)

    def test_browsing_to_idle_on_fist(self) -> None:
        engine = _make_engine()
        engine.state = STATE_BROWSING
        engine._process_transition(GESTURE_FIST)
        self.assertEqual(engine.state, STATE_IDLE)

    def test_browsing_stays_on_swipe(self) -> None:
        engine = _make_engine()
        engine.state = STATE_BROWSING
        engine._process_transition(GESTURE_SWIPE_LEFT)
        self.assertEqual(engine.state, STATE_BROWSING)
        engine._process_transition(GESTURE_SWIPE_RIGHT)
        self.assertEqual(engine.state, STATE_BROWSING)

    def test_selected_to_confirming_on_open_palm(self) -> None:
        engine = _make_engine()
        engine.state = STATE_FILE_SELECTED
        engine._process_transition(GESTURE_OPEN_PALM)
        self.assertEqual(engine.state, STATE_CONFIRMING_SEND)

    def test_selected_to_browsing_on_swipe(self) -> None:
        engine = _make_engine()
        engine.state = STATE_FILE_SELECTED
        engine._process_transition(GESTURE_SWIPE_LEFT)
        self.assertEqual(engine.state, STATE_BROWSING)

    def test_selected_to_idle_on_fist(self) -> None:
        engine = _make_engine()
        engine.state = STATE_FILE_SELECTED
        engine._process_transition(GESTURE_FIST)
        self.assertEqual(engine.state, STATE_IDLE)

    def test_confirming_to_sending_on_pinch(self) -> None:
        engine = _make_engine()
        engine.state = STATE_CONFIRMING_SEND
        engine._process_transition(GESTURE_PINCH)
        self.assertEqual(engine.state, STATE_SENDING)

    def test_confirming_to_selected_on_fist(self) -> None:
        engine = _make_engine()
        engine.state = STATE_CONFIRMING_SEND
        engine._process_transition(GESTURE_FIST)
        self.assertEqual(engine.state, STATE_FILE_SELECTED)

    def test_sending_to_selected_on_fist(self) -> None:
        engine = _make_engine()
        engine.state = STATE_SENDING
        engine._process_transition(GESTURE_FIST)
        self.assertEqual(engine.state, STATE_FILE_SELECTED)

    def test_notify_transfer_complete(self) -> None:
        engine = _make_engine()
        engine.state = STATE_SENDING
        engine.notify_transfer_complete()
        self.assertEqual(engine.state, STATE_SEND_COMPLETE)

    def test_notify_transfer_error(self) -> None:
        engine = _make_engine()
        engine.state = STATE_SENDING
        engine.notify_transfer_error()
        self.assertEqual(engine.state, STATE_FILE_SELECTED)

    def test_send_complete_auto_resets(self) -> None:
        engine = _make_engine()
        engine.state = STATE_SENDING
        engine.notify_transfer_complete()
        # Force the timestamp to the past
        engine._send_complete_time = time.time() - 10
        engine.update([])  # trigger auto-reset check
        self.assertEqual(engine.state, STATE_IDLE)


class TestHysteresis(unittest.TestCase):
    """Test the consecutive-frame hysteresis logic."""

    def test_single_frame_not_enough(self) -> None:
        engine = _make_engine(hysteresis=3, cooldown=0.0)
        # Hysteresis should block with < 3 consecutive frames
        engine._hysteresis[GESTURE_OPEN_PALM] = 1
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, time.time())
        # Count would now be 2, still below 3
        self.assertIsNone(result)

    def test_enough_frames_triggers(self) -> None:
        engine = _make_engine(hysteresis=2, cooldown=0.0)
        now = time.time()
        engine.state = STATE_IDLE  # Open palm is valid in IDLE
        # First call -> count becomes 1
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, now)
        self.assertIsNone(result)
        # Second call -> count becomes 2 (meets threshold)
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, now)
        self.assertEqual(result, GESTURE_OPEN_PALM)


class TestCooldown(unittest.TestCase):
    """Test that per-gesture cooldowns work."""

    def test_cooldown_blocks_repeat(self) -> None:
        engine = _make_engine(hysteresis=1, cooldown=1.0)
        engine.state = STATE_IDLE
        now = time.time()
        # First should succeed
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, now)
        self.assertEqual(result, GESTURE_OPEN_PALM)
        # Immediate repeat should be blocked by cooldown
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, now + 0.1)
        self.assertIsNone(result)

    def test_cooldown_expires(self) -> None:
        engine = _make_engine(hysteresis=1, cooldown=0.5)
        engine.state = STATE_IDLE
        now = time.time()
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, now)
        self.assertEqual(result, GESTURE_OPEN_PALM)
        # After cooldown expires
        result = engine._apply_hysteresis(GESTURE_OPEN_PALM, now + 1.0)
        self.assertEqual(result, GESTURE_OPEN_PALM)


if __name__ == "__main__":
    unittest.main()
