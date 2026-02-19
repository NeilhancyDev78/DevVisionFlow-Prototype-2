# Air Gesture-Controlled File Transfer System

## Target Repository: DevVisionFlow-Prototype-2

---

## 1. Executive Summary

Build a two-node file transfer system where a sender (Dell Inspiron 15) uses webcam-tracked hand gestures via MediaPipe to browse, select, and wirelessly send files to a receiver (Acer Aspire 3) over a custom socket protocol. The receiver listens for incoming transfers and previews files once received. The system extends the gesture detection foundation from DevVisionFlow Prototype 1 with new gestures, a file browser UI, network transport, encryption, and polished UX effects.

---

## 2. Architecture Overview

See README.md for the high-level architecture diagram.

This plan has been implemented. See the source code in:
- `shared/` -- Protocol, encryption, constants
- `sender/` -- Gesture engine, file browser, network transmitter, UI renderer
- `receiver/` -- Network listener, file preview, storage management
- `tests/` -- Unit and integration tests
