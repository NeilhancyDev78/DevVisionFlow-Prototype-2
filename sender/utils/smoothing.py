"""Exponential smoothing filter ported from DevVisionFlow Prototype 1.

Original: DevVisionFLow-Protoype-1/app.py lines 37-47
"""


class SmoothingFilter:
    """Simple exponential smoothing filter for gesture position data."""

    def __init__(self, alpha: float = 0.5, initial_value: float = 0.0) -> None:
        """Initialise the filter.

        Args:
            alpha: Smoothing factor in [0, 1].  0 = maximum smoothing,
                   1 = no smoothing (raw measurements pass through).
            initial_value: Starting value for the filter state.
        """
        self.alpha: float = alpha
        self.value: float = initial_value

    def update(self, measurement: float) -> float:
        """Feed a new measurement and return the smoothed value."""
        self.value = self.alpha * measurement + (1 - self.alpha) * self.value
        return self.value

    def reset(self, value: float = 0.0) -> None:
        """Reset the filter state."""
        self.value = value
