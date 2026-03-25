import numpy as np
import librosa
import soundfile as sf
from mutagen import File as MutagenFile
from PyQt6.QtCore import QThread, pyqtSignal

# Import our new global settings
import config.settings as cfg

class AudioWorker(QThread):
    finished = pyqtSignal(dict) 
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str) 

    def __init__(self, file_path, use_mel=False):
        super().__init__()
        self.file_path = file_path
        self.use_mel = use_mel

    def run(self):
        try:
            self.progress.emit(10, "Reading audio data...")
            try:
                y, sr = sf.read(self.file_path, dtype='float32')
                if y.ndim > 1: 
                    y = y.mean(axis=1) # convert stereo to mono
                duration = len(y) / sr
            except Exception:
                # fallback to librosa if soundfile fails
                y, sr = librosa.load(self.file_path, sr=None, dtype=np.float32)
                duration = librosa.get_duration(y=y, sr=sr)

            self.progress.emit(40, "Processing STFT...")
            
            if self.use_mel:
                S = librosa.feature.melspectrogram(
                    y=y, sr=sr, 
                    n_fft=cfg.N_FFT, 
                    hop_length=cfg.HOP_LENGTH, 
                    n_mels=cfg.N_MELS, 
                    fmax=sr/2.0
                )
                S_db = librosa.power_to_db(S, ref=np.max, top_db=cfg.TOP_DB)
            else:
                D = librosa.stft(y, n_fft=cfg.N_FFT, hop_length=cfg.HOP_LENGTH, window='hann')
                S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max, top_db=cfg.TOP_DB)
            
            max_y, frames = S_db.shape
            
            # downsample if it exceeds our max UI width from settings
            if frames > cfg.MAX_TARGET_WIDTH:
                factor = frames // cfg.MAX_TARGET_WIDTH
                pad_frames = frames - (frames % factor)
                S_db = S_db[:, :pad_frames].reshape(max_y, -1, factor).max(axis=2)
                frames = S_db.shape[1] 

            S_norm = np.clip((S_db + cfg.TOP_DB) / cfg.TOP_DB, 0, 1)
            
            # extract waveform envelope for the minimap
            chunk_size = len(y) // frames
            if chunk_size > 0:
                y_trunc = y[:chunk_size * frames]
                env = np.max(np.abs(y_trunc).reshape(frames, chunk_size), axis=1)
            else:
                env = np.abs(y)
                
            env_norm = env / (np.max(env) + 1e-6) 

            # grab metadata
            audio_meta = MutagenFile(self.file_path)
            if hasattr(audio_meta.info, 'bitrate') and audio_meta.info.bitrate:
                bitrate = f"{int(audio_meta.info.bitrate / 1000)} kbps"
            else:
                bitrate = "VBR/Unknown"
                
            scale_str = "Mel Scale" if self.use_mel else "Linear"
            clean_path = self.file_path.replace('\\', '/')
            metadata = f"{clean_path}\n{bitrate} | {sr} Hz | {scale_str}"

            self.finished.emit({
                's_norm': S_norm, 
                'env_norm': env_norm, 
                'duration': duration, 
                'max_y': max_y, 
                'meta': metadata, 
                'y': y, 
                'sr': sr, 
                'is_mel': self.use_mel
            })
            
        except Exception as e: 
            self.error.emit(str(e))