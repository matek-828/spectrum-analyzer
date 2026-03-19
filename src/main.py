import sys
import time
import numpy as np
import librosa
import sounddevice as sd
import pyqtgraph as pg
import pyqtgraph.exporters
import soundfile as sf
import pyfftw
import scipy.fft
from mutagen import File as MutagenFile
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QFileDialog, QPushButton, QProgressBar, QComboBox)
from PyQt6.QtCore import QRectF, QThread, pyqtSignal, Qt, QTimer

pg.setConfigOptions(antialias=False) 
scipy.fft.set_global_backend(pyfftw.interfaces.scipy_fft)
pyfftw.interfaces.cache.enable()

# =====================================================================
# CUSTOM INTERACTION (Separated Mouse Logic)
# =====================================================================

class CustomViewBox(pg.ViewBox):
    sigResetZoom = pyqtSignal()
    sigLeftClick = pyqtSignal(float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMenuEnabled(False) 
        self.setMouseMode(self.RectMode)

        # Style the default selection box to look like the playhead (White, 2px)
        self.rbScaleBox.setPen(pg.mkPen('#FFFFFF', width=2))
        self.rbScaleBox.setBrush(pg.mkBrush(255, 255, 255, 40))

        # Create the floating text label for the zoom box
        # anchor=(0, 0) means it draws below and to the right of the start point
        self.zoom_text = pg.TextItem("Zoom", color='#FFFFFF', anchor=(0, 0))
        self.zoom_text.setZValue(1000)
        self.addItem(self.zoom_text, ignoreBounds=True)
        self.zoom_text.setVisible(False)

    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
            # Only move the playhead on a clean left click
            pos = self.mapSceneToView(ev.scenePos())
            self.sigLeftClick.emit(pos.x())
        elif ev.button() == Qt.MouseButton.RightButton:
            if ev.double():
                ev.accept()
                self.sigResetZoom.emit()
            else:
                ev.accept()
        else:
            super().mouseClickEvent(ev)

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.MouseButton.RightButton:
            self.setMouseMode(self.RectMode)
            
            # Show the floating text and lock it slightly offset from the mouse cursor
            if ev.isStart():
                self.zoom_text.setVisible(True)
            
            if ev.isFinish():
                self.zoom_text.setVisible(False)
            else:
                pos = self.mapSceneToView(ev.scenePos())
                # Calculate zoom text offset based on overall visible range
                view_range = self.viewRange()[0]
                offset = (view_range[1] - view_range[0]) * 0.01
                self.zoom_text.setPos(pos.x() + offset, pos.y())

            # Safely override the event methods to draw the box using Right-Click coordinates
            orig_btn = ev.button
            orig_bdp = ev.buttonDownPos
            orig_bdsp = ev.buttonDownScenePos
            orig_bdscp = ev.buttonDownScreenPos

            ev.button = lambda: Qt.MouseButton.LeftButton
            ev.buttonDownPos = lambda btn=None: orig_bdp(Qt.MouseButton.RightButton) if btn in (Qt.MouseButton.LeftButton, None) else orig_bdp(btn)
            ev.buttonDownScenePos = lambda btn=None: orig_bdsp(Qt.MouseButton.RightButton) if btn in (Qt.MouseButton.LeftButton, None) else orig_bdsp(btn)
            ev.buttonDownScreenPos = lambda btn=None: orig_bdscp(Qt.MouseButton.RightButton) if btn in (Qt.MouseButton.LeftButton, None) else orig_bdscp(btn)

            super().mouseDragEvent(ev, axis)

            # Restore original methods to prevent cross-event contamination
            ev.button = orig_btn
            ev.buttonDownPos = orig_bdp
            ev.buttonDownScenePos = orig_bdsp
            ev.buttonDownScreenPos = orig_bdscp

        elif ev.button() == Qt.MouseButton.MiddleButton:
            ev.accept()
            # Smooth custom panning logic
            p1 = self.mapToView(ev.pos())
            p2 = self.mapToView(ev.lastPos())
            self.translateBy(x=p2.x() - p1.x(), y=p2.y() - p1.y())
        else:
            ev.ignore()

# =====================================================================
# CUSTOM AXES
# =====================================================================

class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            if v < 0: 
                strings.append("")
            else:
                mins = int(v // 60)
                secs = int(v % 60)
                strings.append(f"{mins}:{secs:02d}")
        return strings

class FreqAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sr = 44100 
        self.max_y = 1025 
        self.is_mel = False
        self.target_hz = [2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000, 18000, 20000, 22000]

    def tickValues(self, minVal, maxVal, size):
        ticks = []
        nyquist = self.sr / 2.0
        
        for hz in self.target_hz:
            if hz <= nyquist:
                if self.is_mel:
                    max_mel = librosa.hz_to_mel(nyquist)
                    current_mel = librosa.hz_to_mel(hz)
                    y_val = (current_mel / max_mel) * self.max_y
                else:
                    y_val = (hz / nyquist) * self.max_y
                    
                if minVal <= y_val <= maxVal + 10: 
                    ticks.append(y_val)
        return [(None, ticks)] 

    def tickStrings(self, values, scale, spacing):
        strings = []
        nyquist = self.sr / 2.0
        
        for v in values:
            if self.is_mel:
                max_mel = librosa.hz_to_mel(nyquist)
                mel_val = (v / self.max_y) * max_mel
                hz = librosa.mel_to_hz(mel_val)
            else:
                hz = (v / self.max_y) * nyquist
                
            closest_hz = min(self.target_hz, key=lambda x: abs(x - hz))
            if closest_hz >= 1000:
                strings.append(f"{int(closest_hz)//1000}k")
            else:
                strings.append(f"{int(closest_hz)}")
        return strings

# =====================================================================
# DIGITAL SIGNAL PROCESSING THREAD
# =====================================================================

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
                    y = y.mean(axis=1)
                duration = len(y) / sr
            except Exception:
                y, sr = librosa.load(self.file_path, sr=None, dtype=np.float32)
                duration = librosa.get_duration(y=y, sr=sr)

            self.progress.emit(40, "Processing STFT...")
            hop_length = 512
            
            if self.use_mel:
                S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=2048, hop_length=hop_length, n_mels=256, fmax=sr/2.0)
                S_db = librosa.power_to_db(S, ref=np.max, top_db=120.0)
            else:
                D = librosa.stft(y, n_fft=2048, hop_length=hop_length, window='hann')
                S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max, top_db=120.0)
            
            max_y, frames = S_db.shape
            
            target_width = 4000
            if frames > target_width:
                factor = frames // target_width
                pad_frames = frames - (frames % factor)
                S_db = S_db[:, :pad_frames].reshape(max_y, -1, factor).max(axis=2)
                frames = S_db.shape[1] 

            S_norm = np.clip((S_db + 120.0) / 120.0, 0, 1)
            
            chunk_size = len(y) // frames
            if chunk_size > 0:
                y_trunc = y[:chunk_size * frames]
                env = np.max(np.abs(y_trunc).reshape(frames, chunk_size), axis=1)
            else:
                env = np.abs(y)
                
            env_norm = env / (np.max(env) + 1e-6) 

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

# =====================================================================
# MAIN APPLICATION CONTROLLER
# =====================================================================

class SpectrumAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectrum Analyzer Pro")
        self.resize(1200, 750)
        self.setAcceptDrops(True)
        self.setStyleSheet("QMainWindow { background-color: #000000; }")

        self.loaded = False
        self.audio_y = None
        self.audio_sr = None
        self.seek_pos = 0.0
        self.play_start = 0.0
        self.is_playing = False
        self.current_duration = 0
        self.current_file_path = ""
        
        self.s_norm = None
        self.env_norm = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_playhead)
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # --- Top Header ---
        header = QHBoxLayout()
        
        self.lbl_meta = QLabel("Drop audio file here to begin...")
        self.lbl_meta.setStyleSheet("font-size: 11px; color: white")
        
        self.lbl_cursor = QLabel("")
        self.lbl_cursor.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_cursor.setStyleSheet("font-size: 12px; color: #00FFCC; font-weight: bold")
        
        header.addWidget(self.lbl_meta)
        header.addStretch()
        header.addWidget(self.lbl_cursor)
        
        layout.addLayout(header)

        # --- Progress Bar ---
        self.bar = QProgressBar()
        self.bar.setFixedHeight(8)
        self.bar.setVisible(False)
        self.bar.setStyleSheet("""
            QProgressBar { border: none; background: #222 } 
            QProgressBar::chunk { background: #00FFCC }
        """)
        layout.addWidget(self.bar)

        # --- Main Graphics View ---
        self.view = pg.GraphicsLayoutWidget()
        layout.addWidget(self.view, stretch=1) 

        # Spectrogram Plot
        self.custom_vb = CustomViewBox()
        self.custom_vb.sigResetZoom.connect(self.reset_zoom)
        self.custom_vb.sigLeftClick.connect(self.seek_from_click)
        
        self.freq_axis = FreqAxisItem(orientation='left')
        self.freq_axis.setWidth(50)
        
        self.plot = self.view.addPlot(row=0, col=0, viewBox=self.custom_vb, axisItems={'bottom': TimeAxisItem(orientation='bottom'), 'left': self.freq_axis})
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.hideButtons()
        self.plot.showGrid(y=True, alpha=0.3)

        self.img = pg.ImageItem()
        self.plot.addItem(self.img)

        # Cutoff Lines - Redesigned anchor to guarantee visibility
        self.lines = []
        cutoff_data = [
            (22050, '22k (Lossless)', '#00FFFF'), 
            (20000, '20k (320k)', '#00FF00'), 
            (16000, '16k (128k)', '#FFFF00')
        ]
        
        for f, l, c in cutoff_data:
            line = pg.InfiniteLine(angle=0, pen=pg.mkPen(color=c, style=Qt.PenStyle.DashLine), label=l, labelOpts={'position':0.05, 'color':c, 'fill':(0,0,0,150), 'anchor':(0, 1)})
            self.plot.addItem(line)
            line.setVisible(False)
            self.lines.append((f, line))

        # Main Playhead & Crosshairs
        self.playhead = pg.InfiniteLine(angle=90, pen=pg.mkPen('#FFFFFF', width=2))
        self.playhead.setZValue(100)
        
        self.vL = pg.InfiniteLine(angle=90, pen=pg.mkPen('#FFFFFF', style=Qt.PenStyle.DashLine))
        self.vL.setZValue(100)
        
        self.hL = pg.InfiniteLine(angle=0, pen=pg.mkPen('#FFFFFF', style=Qt.PenStyle.DashLine))
        self.hL.setZValue(100)

        # Floating Mouse Readout - Initialized to avoid overlap
        self.cursor_label = pg.TextItem("", color='#00FFCC', fill=pg.mkBrush(0, 0, 0, 150))
        self.cursor_label.setZValue(150)
        
        for item in [self.playhead, self.vL, self.hL, self.cursor_label]: 
            self.plot.addItem(item, ignoreBounds=True)
            item.setVisible(False)

        # Waveform Plot
        self.mini_vb = CustomViewBox()
        self.mini_vb.sigResetZoom.connect(self.reset_zoom)
        self.mini_vb.sigLeftClick.connect(self.seek_from_click)
        
        self.mini = self.view.addPlot(row=1, col=0, viewBox=self.mini_vb)
        self.mini.setMaximumHeight(100)
        self.mini.hideAxis('bottom')
        self.mini.setMouseEnabled(x=True, y=False)
        self.mini.setXLink(self.plot)
        
        mini_left = self.mini.getAxis('left')
        mini_left.setWidth(50)
        mini_left.setStyle(showValues=False)
        mini_left.setPen(pg.mkColor(0,0,0,0))
        mini_left.setTextPen(pg.mkColor(0,0,0,0))

        self.mini_img = pg.ImageItem()
        self.mini.addItem(self.mini_img)
        
        self.mini_ph = pg.InfiniteLine(angle=90, pen=pg.mkPen('#FFFFFF', width=2))
        self.mini_ph.setZValue(100) 
        self.mini.addItem(self.mini_ph)
        self.mini_ph.setVisible(False)

        # Crosshair tracking proxy
        self.proxy = pg.SignalProxy(self.view.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse)

        # --- Bottom Toolbar ---
        btns = QHBoxLayout()
        btns.addStretch() 
        
        self.btn_p = QPushButton("Play (Space)")
        self.btn_p.clicked.connect(self.toggle_audio)

        self.btn_scale = QPushButton("Scale: Linear")
        self.btn_scale.clicked.connect(self.toggle_scale)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Theme: DJ", "Theme: Cyberpunk", "Theme: Red", "Theme: Green", "Theme: Blue", "Theme: Monochrome"])
        self.combo_theme.currentIndexChanged.connect(self.apply_theme)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_graph)

        for w in [self.btn_p, self.btn_scale, self.combo_theme, self.btn_clear]:
            w.setEnabled(False)
            if isinstance(w, QComboBox):
                w.setFixedSize(180, 30)
                w.setStyleSheet("""
                    QComboBox { background-color: #333; color: white; border: 1px solid #555; border-radius: 4px; padding-left: 8px; } 
                    QComboBox::drop-down { border: none; } 
                    QComboBox QAbstractItemView { background-color: #333; color: white; selection-background-color: #0078d7; }
                """)
            else:
                w.setFixedSize(140, 30)
                w.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 4px; padding: 5px; }")
            btns.addWidget(w)
            
        btns.addStretch() 
        layout.addLayout(btns)

        cw = QWidget()
        cw.setLayout(layout)
        self.setCentralWidget(cw)

    # --- Themes & Graphics Rendering ---
    def get_theme_colors(self, theme_name):
        # Default initialization
        pos = np.array([0.0, 1.0])
        colors = np.array([[0,0,0,255], [255,255,255,255]], dtype=np.ubyte)
        wave_pos = pos
        wave_colors = colors

        if "Cyberpunk" in theme_name:
            pos = np.array([0.0, 0.33, 0.66, 1.0])
            colors = np.array([[10,0,30,255], [0,255,255,255], [255,0,255,255], [255,255,0,255]], dtype=np.ubyte)
            wave_pos = pos
            wave_colors = colors
            
        elif "Red" in theme_name:
            colors = np.array([[0,0,0,255], [255,0,0,255]], dtype=np.ubyte)
            wave_pos = pos
            wave_colors = colors
            
        elif "Green" in theme_name:
            colors = np.array([[0,0,0,255], [0,255,0,255]], dtype=np.ubyte)
            wave_pos = pos
            wave_colors = colors
            
        elif "Blue" in theme_name:
            colors = np.array([[0,0,0,255], [0,0,255,255]], dtype=np.ubyte)
            wave_pos = pos
            wave_colors = colors
            
        elif "Monochrome" in theme_name:
            colors = np.array([[0,0,0,255], [255,255,255,255]], dtype=np.ubyte)
            wave_pos = pos
            wave_colors = colors
            
        else: 
            # Default DJ Theme
            pos = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
            colors = np.array([
                [255,0,50,255], 
                [255,150,0,255], 
                [0,200,50,255], 
                [0,200,255,255], 
                [0,50,255,255]
            ], dtype=np.ubyte)
            
            wave_pos = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
            wave_colors = np.array([
                [0,0,0,255], 
                [75,0,130,255], 
                [0,0,255,255], 
                [0,255,0,255], 
                [255,255,0,255], 
                [255,0,0,255]
            ], dtype=np.ubyte)

        return pos, colors, wave_pos, wave_colors

    def apply_theme(self):
        if not self.loaded or self.s_norm is None: 
            return

        theme_name = self.combo_theme.currentText()
        pos, colors, w_pos, w_colors = self.get_theme_colors(theme_name)
        
        # Colorize Spectrogram
        cmap = pg.ColorMap(pos, colors)
        y_colors = cmap.getLookupTable(0.0, 1.0, self.max_y)[:, :3] 
        
        rgb_img = self.s_norm[..., np.newaxis] * y_colors[:, np.newaxis, :]
        final_img = np.transpose(rgb_img.astype(np.ubyte), (1, 0, 2))
        self.img.setImage(final_img)

        # Colorize Waveform
        wave_cmap = pg.ColorMap(w_pos, w_colors)
        mapped_colors = wave_cmap.map(self.env_norm) 
        frames = len(self.env_norm)
        h_array = np.clip((self.env_norm * 48).astype(int), 1, 48) 

        minimap = np.zeros((frames, 100, 4), dtype=np.ubyte)
        minimap[:, :, 3] = 255 
        for i in range(frames):
            minimap[i, 50-h_array[i] : 50+h_array[i], :3] = mapped_colors[i, :3]
            
        self.mini_img.setImage(minimap)

    # --- UI Interactions ---
    def toggle_scale(self):
        if not self.current_file_path: 
            return
            
        self.clear_graph()
        self.bar.setValue(0)
        self.bar.setVisible(True)
        
        use_mel = ("Linear" in self.btn_scale.text())
        self.btn_scale.setText(f"Scale: {'Mel' if use_mel else 'Linear'}")
        
        self.worker = AudioWorker(self.current_file_path, use_mel=use_mel)
        self.worker.progress.connect(lambda v, t: (self.bar.setValue(v), self.lbl_meta.setText(t)))
        self.worker.finished.connect(self.on_done)
        self.worker.start()

    def on_mouse(self, e):
        if not self.loaded: 
            return
            
        p = e[0]
        if self.plot.sceneBoundingRect().contains(p):
            mp = self.plot.vb.mapSceneToView(p)
            if 0 <= mp.x() <= self.current_duration and 0 <= mp.y() <= self.max_y:
                self.vL.setVisible(True)
                self.hL.setVisible(True)
                self.cursor_label.setVisible(True)
                
                self.vL.setPos(mp.x())
                self.hL.setPos(mp.y())
                
                if self.freq_axis.is_mel:
                    max_mel = librosa.hz_to_mel(self.audio_sr / 2.0)
                    mel_val = (mp.y() / self.max_y) * max_mel
                    hz = librosa.mel_to_hz(mel_val)
                else:
                    hz = (mp.y() / self.max_y) * (self.audio_sr / 2.0)
                    
                # Format time into MM:SS.ms
                mins = int(mp.x() // 60)
                secs = int(mp.x() % 60)
                ms = int((mp.x() % 1) * 1000)
                
                # Render explicit prefixes 
                self.cursor_label.setText(f"Time: {mins}:{secs:02d}.{ms:03d}\nFreq: {hz/1000:.1f} kHz")
                self.cursor_label.setPos(mp.x(), mp.y())
                
                # Anchor so the text is placed ABOVE and to the LEFT of the crosshair
                # This ensures it never collides with the 'Zoom' box text (which is below-right)
                self.cursor_label.setAnchor((1.1, 1.1))
            else: 
                self.vL.setVisible(False)
                self.hL.setVisible(False)
                self.cursor_label.setVisible(False)

    def seek_from_click(self, x_pos):
        if self.loaded:
            self.seek(max(0, min(x_pos, self.current_duration)))

    def reset_zoom(self):
        if self.loaded:
            self.plot.autoRange()
            self.plot.setXRange(0, self.current_duration, padding=0)
            self.plot.setYRange(0, self.max_y * 1.05, padding=0)
            # Ensure the waveform's vertical axis never shifts from reset
            self.mini.setYRange(0, 100, padding=0)

    def keyPressEvent(self, e):
        if self.loaded:
            if e.key() == Qt.Key.Key_Space: 
                self.toggle_audio()
            elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_A): 
                self.seek(self.seek_pos - 5.0)
            elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_D): 
                self.seek(self.seek_pos + 5.0)

    # --- Audio Engine ---
    def toggle_audio(self):
        if self.is_playing:
            sd.stop()
            self.is_playing = False
            self.timer.stop()
            self.seek_pos += time.time() - self.play_start
            self.btn_p.setText("Play (Space)")
        else:
            sd.play(self.audio_y[int(self.seek_pos * self.audio_sr):], self.audio_sr)
            self.play_start = time.time()
            self.is_playing = True
            self.timer.start(16)
            self.btn_p.setText("Pause (Space)")

    def seek(self, t):
        self.seek_pos = t
        if self.is_playing:
            sd.stop()
            sd.play(self.audio_y[int(t * self.audio_sr):], self.audio_sr)
            self.play_start = time.time()
            
        self.playhead.setPos(t)
        self.mini_ph.setPos(t)

    def update_playhead(self):
        t = self.seek_pos + (time.time() - self.play_start)
        if t >= self.current_duration:
            sd.stop()
            self.is_playing = False
            self.timer.stop()
            self.seek_pos = 0.0
            self.btn_p.setText("Play (Space)")
        else:
            self.playhead.setPos(t)
            self.mini_ph.setPos(t)

    def clear_graph(self):
        sd.stop()
        self.is_playing = False
        self.timer.stop()
        self.img.clear()
        self.mini_img.clear()
        self.loaded = False
        
        self.bar.setVisible(False)
        self.vL.setVisible(False)
        self.hL.setVisible(False)
        self.playhead.setVisible(False)
        self.mini_ph.setVisible(False)
        self.cursor_label.setVisible(False)
        
        self.lbl_meta.setText("Drop audio file here to begin...")
        
        for _, l in self.lines: 
            l.setVisible(False)
            
        for w in [self.btn_p, self.btn_scale, self.combo_theme, self.btn_clear]: 
            w.setEnabled(False)

    def dragEnterEvent(self, e): 
        if e.mimeData().hasUrls(): 
            e.acceptProposedAction()

    def dropEvent(self, e):
        path = e.mimeData().urls()[0].toLocalFile()
        if path.lower().endswith(('.wav', '.flac', '.mp3', '.ogg', '.m4a')):
            self.clear_graph()
            self.current_file_path = path
            self.bar.setValue(0)
            self.bar.setVisible(True)
            
            use_mel = ("Mel" in self.btn_scale.text())
            self.worker = AudioWorker(path, use_mel=use_mel)
            self.worker.progress.connect(lambda v, t: (self.bar.setValue(v), self.lbl_meta.setText(t)))
            self.worker.finished.connect(self.on_done)
            self.worker.start()

    def on_done(self, d):
        self.bar.setVisible(False)
        self.current_duration = d['duration']
        self.max_y = d['max_y']
        
        self.audio_y = d['y']
        self.audio_sr = d['sr']
        self.s_norm = d['s_norm']
        self.env_norm = d['env_norm']
        
        self.freq_axis.sr = self.audio_sr
        self.freq_axis.max_y = self.max_y
        self.freq_axis.is_mel = d['is_mel']
        
        for f, l in self.lines:
            if self.freq_axis.is_mel:
                max_mel = librosa.hz_to_mel(self.audio_sr / 2.0)
                mel_val = librosa.hz_to_mel(f)
                y_pos = (mel_val / max_mel) * self.max_y
            else:
                y_pos = (f / (self.audio_sr / 2.0)) * self.max_y
                
            if f <= (self.audio_sr / 2):
                l.setPos(y_pos)
                l.setVisible(True)
                
        self.loaded = True
        self.apply_theme()
        
        self.img.setRect(QRectF(0, 0, self.current_duration, self.max_y))
        
        self.plot.setLimits(xMin=0, xMax=self.current_duration, yMin=0, yMax=self.max_y * 1.05, minXRange=15.0)
        self.plot.setYRange(0, self.max_y * 1.05, padding=0)
        self.plot.autoRange()
        
        self.mini_img.setRect(QRectF(0, 0, self.current_duration, 100))
        # Physically lock the waveform's vertical axis so Box Zoom cannot affect it
        self.mini.setLimits(xMin=0, xMax=self.current_duration, yMin=0, yMax=100, minYRange=100, maxYRange=100)
        self.mini.setYRange(0, 100, padding=0)
        
        self.lbl_meta.setText(d['meta'])
        self.playhead.setVisible(True)
        self.mini_ph.setVisible(True)
        
        for w in [self.btn_p, self.btn_scale, self.combo_theme, self.btn_clear]: 
            w.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpectrumAnalyzerApp()
    window.show()
    sys.exit(app.exec())