#  Spectrum Analyzer Pro

A high-performance desktop audio visualization tool built in **Python**, designed for real-time spectrogram analysis, waveform inspection, and audio playback.

![ababa0da-934d-4f6f-925d-17deacb2dda0](https://github.com/user-attachments/assets/38c719cd-6d56-4952-866e-171a502509f7)

---

##  Overview

Spectrum Analyzer Pro is an interactive desktop application that allows users to:

- Visualize audio in both **time and frequency domains**
- Analyze spectral content using **STFT and Mel spectrograms**
- Detect **audio quality loss (e.g. MP3 vs lossless)**
- Interact with audio using a fully custom UI

---

##  Key Features

###  Audio Processing
- STFT-based spectrogram using **Librosa**
- Optional **Mel-scale transformation**
- FFT acceleration via **pyFFTW**
- Automatic downsampling for large audio files

###  Playback Engine
- Built-in audio playback using **SoundDevice**
- Real-time synchronized playhead
- Seek via:
  - Mouse click
  - Keyboard controls

###  Visualization
- High-performance rendering with **PyQtGraph**
- Interactive features:
  - Zoom (Right-click drag)
  - Pan (Middle-click drag)
  - Reset zoom (Right double-click)
- Crosshair cursor with:
  - Time (ms precision)
  - Frequency (kHz)

###  Custom UI & Themes
- Multiple color themes:
  - DJ (default)
  - Cyberpunk
  - Red / Green / Blue
  - Monochrome
- Custom ViewBox for advanced mouse interaction

###  Audio Quality Detection
- Frequency cutoff guides:
  - **16 kHz** → typical 128 kbps MP3
  - **20 kHz** → 320 kbps MP3
  - **22 kHz** → lossless audio
- Helps identify:
  - Fake WAV files
  - Upscaled audio

###  File Support
- Drag & Drop interface
- Supported formats:
  - `.wav`, `.flac`, `.mp3`, `.ogg`, `.m4a`

---

##  Tech Stack

- **Python**
- **PyQt6** – GUI framework
- **PyQtGraph** – real-time visualization
- **Librosa** – audio analysis
- **SoundDevice** – playback engine
- **SoundFile** – audio decoding
- **pyFFTW + SciPy FFT** – optimized FFT
- **Mutagen** – metadata extraction
- **NumPy** – numerical processing

---

##  Installation

```bash
git clone https://github.com/matek-828/spectrum-analyzer.git
cd spectrum-analyzer
pip install -r requirements.txt
