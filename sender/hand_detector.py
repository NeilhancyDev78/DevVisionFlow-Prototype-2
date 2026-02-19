"""Hand detection wrapper using MediaPipe Hands.

Ported from DevVisionFLow-Protoype-1/app.py lines 50-82 with minor
adjustments for the Prototype 2 config structure.
"""

import logging
from typing import List, Tuple

import cv2
import mediapipe as mp
import numpy as np

from sender.config import SenderConfig

logger = logging.getLogger(__name__)


class HandDetector:
    """Detects a single hand and returns 21 landmark coordinates."""

    def __init__(self, config: SenderConfig) -> None:
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.config = config
        self._results = None

    def find_hands(
        self, img: np.ndarray
    ) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
        """Process an image and return (annotated_image, landmark_list).

        Each landmark in *landmark_list* is an ``(x, y)`` pixel coordinate
        tuple.  The list contains 21 entries when a hand is detected, or is
        empty otherwise.
        """
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._results = self.hands.process(img_rgb)
        landmark_list: List[Tuple[int, int]] = []

        if self._results.multi_hand_landmarks:
            hand = self._results.multi_hand_landmarks[0]
            h, w, _c = img.shape
            for lm in hand.landmark:
                cx, cy = int(lm.x * w), int(lm.y * h)
                landmark_list.append((cx, cy))

            if self.config.show_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    img, hand, self.mp_hands.HAND_CONNECTIONS
                )

        return img, landmark_list

    def release(self) -> None:
        """Release MediaPipe resources."""
        self.hands.close()
