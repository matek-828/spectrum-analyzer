import numpy as np

def downsample_spectrogram(S_db, max_target_width):
    """
    Reduces the horizontal resolution of a spectrogram to prevent UI freezing.
    Uses 'max' downsampling to ensure transient details (like drum hits) are retained.
    """
    max_y, frames = S_db.shape
    
    if frames <= max_target_width:
        return S_db, frames
        
    factor = frames // max_target_width
    pad_frames = frames - (frames % factor)
    
    # Reshape and take the maximum value across the chunk to preserve peaks
    downsampled_S = S_db[:, :pad_frames].reshape(max_y, -1, factor).max(axis=2)
    
    return downsampled_S, downsampled_S.shape[1]

def calculate_waveform_envelope(y, frames):
    """
    Extracts the visual envelope of the raw audio waveform to perfectly 
    match the horizontal frame count of the spectrogram for the UI minimap.
    """
    chunk_size = len(y) // frames
    
    if chunk_size > 0:
        y_trunc = y[:chunk_size * frames]
        env = np.max(np.abs(y_trunc).reshape(frames, chunk_size), axis=1)
    else:
        env = np.abs(y)
        
    # Normalize between 0.0 and 1.0 safely
    env_norm = env / (np.max(env) + 1e-6)
    
    return env_norm