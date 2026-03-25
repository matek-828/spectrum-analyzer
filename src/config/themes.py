import numpy as np

def get_theme_colors(theme_name):
    # defaults (monochrome)
    pos = np.array([0.0, 1.0])
    colors = np.array([[0, 0, 0, 255], [255, 255, 255, 255]], dtype=np.ubyte)
    w_pos, w_colors = pos, colors

    if "Cyberpunk" in theme_name:
        pos = np.array([0.0, 0.33, 0.66, 1.0])
        colors = np.array([
            [10, 0, 30, 255], [0, 255, 255, 255], 
            [255, 0, 255, 255], [255, 255, 0, 255]
        ], dtype=np.ubyte)
        w_pos, w_colors = pos, colors
        
    elif "Red" in theme_name:
        colors = np.array([[0, 0, 0, 255], [255, 0, 0, 255]], dtype=np.ubyte)
        w_pos, w_colors = pos, colors
        
    elif "Green" in theme_name:
        colors = np.array([[0, 0, 0, 255], [0, 255, 0, 255]], dtype=np.ubyte)
        w_pos, w_colors = pos, colors
        
    elif "Blue" in theme_name:
        colors = np.array([[0, 0, 0, 255], [0, 0, 255, 255]], dtype=np.ubyte)
        w_pos, w_colors = pos, colors
        
    elif "Monochrome" in theme_name:
        pass # uses defaults
        
    else: 
        # dj theme
        pos = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        colors = np.array([
            [255, 0, 50, 255], [255, 150, 0, 255], 
            [0, 200, 50, 255], [0, 200, 255, 255], [0, 50, 255, 255]
        ], dtype=np.ubyte)
        
        w_pos = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
        w_colors = np.array([
            [0, 0, 0, 255], [75, 0, 130, 255], [0, 0, 255, 255], 
            [0, 255, 0, 255], [255, 255, 0, 255], [255, 0, 0, 255]
        ], dtype=np.ubyte)

    return pos, colors, w_pos, w_colors