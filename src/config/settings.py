# window & styling
APP_TITLE = "Spectrum Analyzer Pro"
WINDOW_START_WIDTH = 1200
WINDOW_START_HEIGHT = 750
BG_COLOR = "#000000"
TEXT_COLOR = "#FFFFFF"
ACCENT_COLOR = "#00FFCC"

# dsp parameters
N_FFT = 2048
HOP_LENGTH = 512
N_MELS = 256
TOP_DB = 120.0

# limits
MAX_TARGET_WIDTH = 4000 # prevent freezing on long tracks
TIMER_INTERVAL_MS = 16  # approx 60fps

SUPPORTED_AUDIO_FORMATS = ('.wav', '.flac', '.mp3', '.ogg', '.m4a')

# y-axis ticks in Hz
TARGET_HZ_TICKS = [2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000, 18000, 20000, 22000]

# reference lines for mp3 compression (freq, label, color)
QUALITY_CUTOFF_LINES = [
    (22050, '22k (Lossless)', '#00FFFF'), 
    (20000, '20k (320k)', '#00FF00'), 
    (16000, '16k (128k)', '#FFFF00')
]