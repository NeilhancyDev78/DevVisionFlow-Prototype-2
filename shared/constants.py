"""Constants shared across sender and receiver modules."""

# Protocol constants
MAGIC_NUMBER: bytes = b'\xDE\x0F'  # DevisionFlow magic (2 bytes, padded to 4)
MAGIC_NUMBER_FULL: bytes = b'\x00\x00\xDE\x0F'  # 4-byte magic
PROTOCOL_VERSION: int = 0x02
HEADER_SIZE: int = 256

# Message types
MSG_HANDSHAKE: int = 0x01
MSG_FILE_META: int = 0x02
MSG_CHUNK: int = 0x03
MSG_ACK: int = 0x04
MSG_ERROR: int = 0x05
MSG_DONE: int = 0x06

# Network defaults
DEFAULT_PORT: int = 9876
DISCOVERY_PORT: int = 9875
DEFAULT_CHUNK_SIZE: int = 65536  # 64 KB
LARGE_FILE_CHUNK_SIZE: int = 262144  # 256 KB
LARGE_FILE_THRESHOLD: int = 1073741824  # 1 GB

# Timeout and retry
MAX_RETRIES: int = 3
CHUNK_TIMEOUT: float = 10.0  # seconds
HANDSHAKE_TIMEOUT: float = 30.0  # seconds
ACK_TIMEOUT: float = 10.0  # seconds

# Gesture cooldowns (seconds)
COOLDOWN_OPEN_PALM: float = 1.5
COOLDOWN_SWIPE: float = 0.6
COOLDOWN_PINCH: float = 1.0
COOLDOWN_FIST: float = 1.0
COOLDOWN_TWO_FINGER: float = 0.8

# Gesture detection
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.85
DEFAULT_HYSTERESIS_FRAMES: int = 3

# State machine states
STATE_IDLE: str = "IDLE"
STATE_BROWSING: str = "BROWSING"
STATE_FILE_SELECTED: str = "FILE_SELECTED"
STATE_CONFIRMING_SEND: str = "CONFIRMING_SEND"
STATE_SENDING: str = "SENDING"
STATE_SEND_COMPLETE: str = "SEND_COMPLETE"

# Gesture names
GESTURE_OPEN_PALM: str = "Open Palm"
GESTURE_SWIPE_LEFT: str = "Swipe Left"
GESTURE_SWIPE_RIGHT: str = "Swipe Right"
GESTURE_PINCH: str = "Pinch"
GESTURE_FIST: str = "Fist"
GESTURE_TWO_FINGER: str = "Two Finger Point"
GESTURE_NONE: str = "None"

# Display settings
DEFAULT_FRAME_WIDTH: int = 640
DEFAULT_FRAME_HEIGHT: int = 480

# UI colors (BGR format for OpenCV)
COLOR_IDLE: tuple = (128, 128, 128)       # Gray
COLOR_BROWSING: tuple = (255, 128, 0)     # Blue
COLOR_SELECTED: tuple = (0, 255, 255)     # Yellow
COLOR_CONFIRMING: tuple = (0, 200, 255)   # Orange
COLOR_SENDING: tuple = (0, 255, 0)        # Green
COLOR_COMPLETE: tuple = (0, 255, 0)       # Green
COLOR_ERROR: tuple = (0, 0, 255)          # Red
COLOR_TEXT: tuple = (255, 255, 255)        # White
COLOR_HIGHLIGHT: tuple = (255, 200, 0)    # Cyan-ish
COLOR_CONNECTED: tuple = (0, 255, 0)      # Green
COLOR_CONNECTING: tuple = (0, 255, 255)   # Yellow
COLOR_DISCONNECTED: tuple = (0, 0, 255)   # Red

# State to color mapping
STATE_COLORS: dict = {
    STATE_IDLE: COLOR_IDLE,
    STATE_BROWSING: COLOR_BROWSING,
    STATE_FILE_SELECTED: COLOR_SELECTED,
    STATE_CONFIRMING_SEND: COLOR_CONFIRMING,
    STATE_SENDING: COLOR_SENDING,
    STATE_SEND_COMPLETE: COLOR_COMPLETE,
}

# Auto-reset delay for SEND_COMPLETE state
SEND_COMPLETE_RESET_DELAY: float = 3.0

# Keypoint classifier label mapping (from Prototype 1)
# 0: Open, 1: Close, 2: Pointer, 3: OK
KEYPOINT_OPEN: int = 0
KEYPOINT_CLOSE: int = 1
KEYPOINT_POINTER: int = 2
KEYPOINT_OK: int = 3

# Point history classifier label mapping (from Prototype 1)
# 0: Stop, 1: Clockwise, 2: Counter Clockwise, 3: Move
POINT_HISTORY_STOP: int = 0
POINT_HISTORY_CLOCKWISE: int = 1
POINT_HISTORY_COUNTER_CLOCKWISE: int = 2
POINT_HISTORY_MOVE: int = 3
