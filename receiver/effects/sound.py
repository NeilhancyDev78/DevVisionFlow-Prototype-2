"""Sound cue manager for the receiver (mirrors sender/effects/sound.py)."""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import pygame
    import pygame.mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logger.info("pygame not installed -- sound cues disabled")


class SoundManager:
    """Loads and plays WAV sound cues for the receiver."""

    _SOUND_FILES: Dict[str, str] = {
        "incoming": "incoming.wav",
        "complete": "success.wav",
        "error": "error.wav",
    }

    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.5,
        sounds_dir: Optional[str] = None,
    ) -> None:
        self._enabled = enabled and PYGAME_AVAILABLE
        self._sounds: Dict[str, object] = {}
        self._volume = max(0.0, min(1.0, volume))

        if not self._enabled:
            return

        try:
            pygame.mixer.init()
        except Exception as exc:
            logger.warning("Could not initialise pygame.mixer: %s", exc)
            self._enabled = False
            return

        if sounds_dir is None:
            sounds_dir = str(Path(__file__).resolve().parent.parent / "assets" / "sounds")

        self._load_sounds(Path(sounds_dir))

    def _load_sounds(self, directory: Path) -> None:
        for key, filename in self._SOUND_FILES.items():
            filepath = directory / filename
            if filepath.exists():
                try:
                    snd = pygame.mixer.Sound(str(filepath))
                    snd.set_volume(self._volume)
                    self._sounds[key] = snd
                except Exception as exc:
                    logger.warning("Failed to load sound %s: %s", filepath, exc)

    def play(self, event: str) -> None:
        if not self._enabled:
            return
        snd = self._sounds.get(event)
        if snd:
            try:
                snd.play()
            except Exception as exc:
                logger.debug("Sound playback failed for %s: %s", event, exc)

    def shutdown(self) -> None:
        if self._enabled and PYGAME_AVAILABLE:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
