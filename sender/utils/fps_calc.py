"""FPS calculator ported from DevVisionFlow Prototype 1.

Original: DevVisionFLow-Protoype-1/utils/cvfpscalc.py
"""

from collections import deque

import cv2 as cv


class CvFpsCalc:
    """Calculates a running-average frames-per-second value."""

    def __init__(self, buffer_len: int = 1) -> None:
        self._start_tick: int = cv.getTickCount()
        self._freq: float = 1000.0 / cv.getTickFrequency()
        self._difftimes: deque = deque(maxlen=buffer_len)

    def get(self) -> float:
        """Return the current smoothed FPS value."""
        current_tick = cv.getTickCount()
        different_time = (current_tick - self._start_tick) * self._freq
        self._start_tick = current_tick

        self._difftimes.append(different_time)

        fps = 1000.0 / (sum(self._difftimes) / len(self._difftimes))
        return round(fps, 2)
