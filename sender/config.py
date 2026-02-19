"""Extended configuration dataclass for the sender application.

Builds on the Prototype 1 Config pattern with additional settings for
networking, encryption, file browsing, and UX effects.
"""

from dataclasses import dataclass, field
from pathlib import Path

from shared.constants import (
    COOLDOWN_FIST,
    COOLDOWN_OPEN_PALM,
    COOLDOWN_PINCH,
    COOLDOWN_SWIPE,
    COOLDOWN_TWO_FINGER,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DEFAULT_HYSTERESIS_FRAMES,
    DEFAULT_PORT,
)


@dataclass
class SenderConfig:
    """Configuration for the sender application."""

    # --- Display ---
    frame_width: int = DEFAULT_FRAME_WIDTH
    frame_height: int = DEFAULT_FRAME_HEIGHT
    show_fps: bool = True
    show_hand_landmarks: bool = True
    show_gesture_info: bool = True

    # --- Hand detection ---
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.7
    model_complexity: int = 0  # 0 for speed, 1 for accuracy

    # --- Gesture detection ---
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    hysteresis_frames: int = DEFAULT_HYSTERESIS_FRAMES
    smoothing_factor: float = 0.5

    # --- Per-gesture cooldowns ---
    cooldown_open_palm: float = COOLDOWN_OPEN_PALM
    cooldown_swipe: float = COOLDOWN_SWIPE
    cooldown_pinch: float = COOLDOWN_PINCH
    cooldown_fist: float = COOLDOWN_FIST
    cooldown_two_finger: float = COOLDOWN_TWO_FINGER

    # --- File browser ---
    send_directory: str = field(default_factory=lambda: str(Path.home() / "SendBox"))

    # --- Network ---
    receiver_host: str = "127.0.0.1"
    receiver_port: int = DEFAULT_PORT
    chunk_size: int = DEFAULT_CHUNK_SIZE

    # --- Encryption ---
    encryption_enabled: bool = False

    # --- Sound ---
    sound_enabled: bool = True
    sound_volume: float = 0.5

    # --- Model paths ---
    keypoint_model_path: str = "sender/model/keypoint_classifier/keypoint_classifier.tflite"
    keypoint_label_path: str = "sender/model/keypoint_classifier/keypoint_classifier_label.csv"
    point_history_model_path: str = (
        "sender/model/point_history_classifier/point_history_classifier.tflite"
    )
    point_history_label_path: str = (
        "sender/model/point_history_classifier/point_history_classifier_label.csv"
    )

    # --- Debug ---
    debug: bool = False
