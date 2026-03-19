# Spectrum Analyzer Pro

A high-performance, professional-grade audio spectrum analyzer built with Python, PyQt6, and librosa. Optimized for accuracy and real-time visual weight.

## Key Features
- **GPU-Accelerated Rendering:** Uses LUT (Look-Up Table) logic for near-instant theme swaps and fluid zooming.
- **Sample-Accurate Playback:** Low-latency hardware callback stream ensures the playhead never drifts from the audio.
- **Hybrid Downsampling:** Custom 70/30 Mean/Peak engine preserves both transients and the "body" of the sound.
- **DJ-Ready Visuals:** High-contrast themes (DJ, Cyberpunk, Monochrome) and scientific scale toggling (Linear/Mel).

## Controls
- **Left Click:** Set Playhead
- **Right Click + Drag:** Zoom Selection
- **Double Right Click:** Reset View
- **Spacebar:** Play/Pause

## Installation
1. Install dependencies: `pip install PyQt6 pyqtgraph librosa sounddevice mutagen soundfile pyfftw scipy`
2. Run: `python src/main.py`
