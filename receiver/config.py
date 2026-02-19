"""Configuration dataclass for the receiver application."""

from dataclasses import dataclass, field
from pathlib import Path

from shared.constants import DEFAULT_PORT


@dataclass
class ReceiverConfig:
    """Configuration for the receiver application."""

    # --- Network ---
    listen_host: str = "0.0.0.0"
    listen_port: int = DEFAULT_PORT

    # --- Storage ---
    receive_directory: str = field(
        default_factory=lambda: str(Path.home() / "ReceivedFiles")
    )

    # --- Encryption ---
    encryption_enabled: bool = False

    # --- Preview ---
    auto_preview: bool = True

    # --- Sound ---
    sound_enabled: bool = True
    sound_volume: float = 0.5

    # --- Debug ---
    debug: bool = False
