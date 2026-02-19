# DevVisionFlow Prototype 2 -- Air Gesture-Controlled File Transfer

A two-node file transfer system where the **sender** uses webcam-tracked hand gestures (via MediaPipe) to browse, select, and wirelessly send files to a **receiver** over a custom socket protocol. The receiver listens for incoming transfers and previews files once received.

Built on the gesture detection foundation from [DevVisionFlow Prototype 1](https://github.com/NeilhancyDev78/DevVisionFLow-Protoype-1).

---

## Features

- **6-gesture vocabulary**: Open Palm, Swipe Left/Right, Pinch, Fist, Two-Finger Point
- **6-state FSM**: IDLE, BROWSING, FILE_SELECTED, CONFIRMING_SEND, SENDING, SEND_COMPLETE
- **Custom binary protocol** over TCP with SHA-256 integrity checks per message
- **Chunked transfer** with per-chunk ACKs and retry logic (64 KB default chunks)
- **Optional AES-256-GCM encryption** with X25519 key exchange
- **OpenCV overlay UI**: file browser, gesture glow effects, progress arc, state badge
- **Sound cues** via pygame.mixer (optional, graceful fallback)
- **Auto-preview** on receiver: images via OpenCV, text files, system-default for others
- **Per-gesture cooldowns** and consecutive-frame hysteresis to eliminate false positives

---

## Architecture

```
Sender (Dell Inspiron 15)          Receiver (Acer Aspire 3)
+------------------+               +------------------+
| Webcam -> MP     |               | TCP Listener     |
| Gesture Engine   |               | Decryption       |
| File Browser UI  |   TCP/9876    | File Storage     |
| Encryption       | ------------> | File Preview     |
| Socket TX        |               | Notifications    |
+------------------+               +------------------+
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- Webcam (sender only)

### Installation

```bash
pip install -r requirements.txt
```

### Run the Receiver

```bash
python -m receiver.main
```

The receiver listens on port 9876 by default. Received files are saved to `~/ReceivedFiles/`.

### Run the Sender

```bash
python -m sender.main
```

The sender opens your webcam and displays the gesture-controlled file browser overlay. Files are read from `~/SendBox/` -- create this directory and place files in it before starting.

### Gesture Controls

| Gesture | Action |
|---------|--------|
| **Open Palm** | Enter file browser / Initiate send |
| **Swipe Left** | Previous file |
| **Swipe Right** | Next file |
| **Pinch** | Select file / Confirm send |
| **Fist** | Cancel / Go back |
| **Two-Finger Point** | Toggle file details |

Press **q** to quit the sender.

---

## Project Structure

```
DevVisionFlow-Prototype-2/
    shared/              # Protocol, encryption, constants
    sender/
        main.py          # Sender entry point
        hand_detector.py # MediaPipe wrapper
        gesture_engine.py # State machine + gesture classification
        file_browser.py  # Directory listing and navigation
        ui_renderer.py   # OpenCV overlay rendering
        network/         # Socket transmitter
        effects/         # Sound cues
        model/           # TFLite classifiers (from Prototype 1)
        utils/           # FPS calc, smoothing filter
    receiver/
        main.py          # Receiver entry point
        network/         # Socket listener
        preview/         # File preview engine
        effects/         # Sound cues
        storage/         # File management
    tests/               # Unit and integration tests
```

---

## Configuration

Both sender and receiver use Python dataclasses for configuration. Key settings:

**Sender** (`sender/config.py`):
- `send_directory`: Path to files to send (default: `~/SendBox/`)
- `receiver_host` / `receiver_port`: Receiver address (default: `127.0.0.1:9876`)
- `encryption_enabled`: Toggle AES-256-GCM encryption
- `confidence_threshold`: Gesture confidence threshold (default: 0.85)
- `hysteresis_frames`: Consecutive frames required before triggering (default: 3)

**Receiver** (`receiver/config.py`):
- `listen_host` / `listen_port`: Bind address (default: `0.0.0.0:9876`)
- `receive_directory`: Where to save files (default: `~/ReceivedFiles/`)
- `auto_preview`: Auto-open preview on receive (default: true)

---

## Testing

```bash
cd DevVisionFlow-Prototype-2
python -m pytest tests/ -v
```

Tests cover:
- Protocol serialisation/deserialisation round-trips
- Gesture state machine transitions
- File browser navigation
- Localhost file transfer integration

---

## Components Ported from Prototype 1

| Component | Adaptation |
|-----------|-----------|
| `SmoothingFilter` | Reused as-is |
| `CvFpsCalc` | Reused as-is |
| `HandDetector` | Updated for new config structure |
| `GestureDetector` | Replaced with state-machine-based `GestureEngine` |
| Keypoint classifier labels | Open -> Open Palm, Close -> Fist |
| Point history classifier | Used for swipe detection |

---

## License

See the repository license file for details.
