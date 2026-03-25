import time
import numpy as np
import librosa
import sounddevice as sd
import pyqtgraph as pg

from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QProgressBar, QMessageBox
from PyQt6.QtCore import QRectF, Qt, QTimer

# Modular Imports
import config.settings as cfg
from config.themes import get_theme_colors
from ui.widgets.custom_graphs import CustomViewBox, TimeAxisItem, FreqAxisItem
from ui.widgets.control_bar import ControlBar
from ui.dialogs.export_dialog import ExportDialog
from core.audio_worker import AudioWorker
from core.exporter import ExportWorker

class SpectrumAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(cfg.APP_TITLE)
        self.resize(cfg.WINDOW_START_WIDTH, cfg.WINDOW_START_HEIGHT)
        self.setAcceptDrops(True)
        self.setStyleSheet(f"QMainWindow {{ background-color: {cfg.BG_COLOR}; }}")

        # State Variables
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
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QHBoxLayout()
        self.lbl_meta = QLabel("Drop audio file here to begin...")
        self.lbl_meta.setStyleSheet("font-size: 11px; color: white")
        self.lbl_cursor = QLabel("")
        self.lbl_cursor.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_cursor.setStyleSheet(f"font-size: 12px; color: {cfg.ACCENT_COLOR}; font-weight: bold")
        
        header.addWidget(self.lbl_meta)
        header.addStretch()
        header.addWidget(self.lbl_cursor)
        layout.addLayout(header)

        # Progress
        self.bar = QProgressBar()
        self.bar.setFixedHeight(8)
        self.bar.setVisible(False)
        self.bar.setStyleSheet(f"QProgressBar {{ border: none; background: #222 }} QProgressBar::chunk {{ background: {cfg.ACCENT_COLOR} }}")
        layout.addWidget(self.bar)

        # Graphs
        self.view = pg.GraphicsLayoutWidget()
        layout.addWidget(self.view, stretch=1) 

        # Main Spectrogram
        self.custom_vb = CustomViewBox()
        self.custom_vb.sigResetZoom.connect(self.reset_zoom)
        self.custom_vb.sigLeftClick.connect(self.seek_from_click)
        self.freq_axis = FreqAxisItem(orientation='left')
        self.freq_axis.setWidth(50)
        
        self.plot = self.view.addPlot(row=0, col=0, viewBox=self.custom_vb, 
                                     axisItems={'bottom': TimeAxisItem(orientation='bottom'), 'left': self.freq_axis})
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.hideButtons()
        self.plot.showGrid(y=True, alpha=0.3)

        self.img = pg.ImageItem()
        self.plot.addItem(self.img)

        # Quality Cutoff Lines
        self.lines = []
        for f, l, c in cfg.QUALITY_CUTOFF_LINES:
            line = pg.InfiniteLine(angle=0, pen=pg.mkPen(color=c, style=Qt.PenStyle.DashLine), 
                                  label=l, labelOpts={'position':0.05, 'color':c, 'fill':(0,0,0,150), 'anchor':(0, 1)})
            self.plot.addItem(line)
            line.setVisible(False)
            self.lines.append((f, line))

        # Visual Overlays
        self.playhead = pg.InfiniteLine(angle=90, pen=pg.mkPen('#FFFFFF', width=2))
        self.vL = pg.InfiniteLine(angle=90, pen=pg.mkPen('#FFFFFF', style=Qt.PenStyle.DashLine))
        self.hL = pg.InfiniteLine(angle=0, pen=pg.mkPen('#FFFFFF', style=Qt.PenStyle.DashLine))
        self.cursor_label = pg.TextItem("", color=cfg.ACCENT_COLOR, fill=pg.mkBrush(0, 0, 0, 150))
        
        for item in [self.playhead, self.vL, self.hL, self.cursor_label]: 
            item.setZValue(150)
            self.plot.addItem(item, ignoreBounds=True)
            item.setVisible(False)

        # Mini Waveform
        self.mini_vb = CustomViewBox()
        self.mini_vb.sigResetZoom.connect(self.reset_zoom)
        self.mini_vb.sigLeftClick.connect(self.seek_from_click)
        self.mini = self.view.addPlot(row=1, col=0, viewBox=self.mini_vb)
        self.mini.setMaximumHeight(100)
        self.mini.hideAxis('bottom')
        self.mini.setMouseEnabled(x=True, y=False)
        self.mini.setXLink(self.plot)
        self.mini.getAxis('left').setWidth(50)
        self.mini.getAxis('left').setStyle(showValues=False)

        self.mini_img = pg.ImageItem()
        self.mini.addItem(self.mini_img)
        self.mini_ph = pg.InfiniteLine(angle=90, pen=pg.mkPen('#FFFFFF', width=2))
        self.mini.addItem(self.mini_ph)
        self.mini_ph.setVisible(False)

        self.proxy = pg.SignalProxy(self.view.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse)

        # NEW: The Modular Control Bar
        self.controls = ControlBar()
        self.controls.sig_play.connect(self.toggle_audio)
        self.controls.sig_scale.connect(self.toggle_scale)
        self.controls.sig_theme.connect(self.apply_theme)
        self.controls.sig_export.connect(self.show_export_dialog)
        self.controls.sig_clear.connect(self.clear_graph)
        layout.addWidget(self.controls)

        self.setCentralWidget(central_widget)

    def show_export_dialog(self):
        if not self.loaded: return
        
        dialog = ExportDialog(self.current_duration, self)
        if dialog.exec():
            start, end, path = dialog.get_export_params()
            self.lbl_meta.setText(f"Exporting snippet to {path}...")
            
            self.export_worker = ExportWorker(self.audio_y, self.audio_sr, start, end, path)
            self.export_worker.finished.connect(lambda p: QMessageBox.information(self, "Success", f"Exported: {p}"))
            self.export_worker.error.connect(lambda e: QMessageBox.critical(self, "Export Error", e))
            self.export_worker.start()

    def apply_theme(self):
        if not self.loaded: return
        theme_name = self.controls.get_current_theme()
        pos, colors, w_pos, w_colors = get_theme_colors(theme_name)
        
        cmap = pg.ColorMap(pos, colors)
        y_colors = cmap.getLookupTable(0.0, 1.0, self.max_y)[:, :3] 
        rgb_img = self.s_norm[..., np.newaxis] * y_colors[:, np.newaxis, :]
        self.img.setImage(np.transpose(rgb_img.astype(np.ubyte), (1, 0, 2)))

        wave_cmap = pg.ColorMap(w_pos, w_colors)
        mapped_colors = wave_cmap.map(self.env_norm) 
        h_array = np.clip((self.env_norm * 48).astype(int), 1, 48) 
        minimap = np.zeros((len(self.env_norm), 100, 4), dtype=np.ubyte)
        minimap[:, :, 3] = 255 
        for i in range(len(self.env_norm)):
            minimap[i, 50-h_array[i] : 50+h_array[i], :3] = mapped_colors[i, :3]
        self.mini_img.setImage(minimap)

    def toggle_scale(self):
        if not self.current_file_path: return
        use_mel = self.controls.toggle_scale_text()
        self.load_audio(self.current_file_path, use_mel)

    def load_audio(self, path, use_mel):
        self.clear_graph()
        self.current_file_path = path
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self.worker = AudioWorker(path, use_mel=use_mel)
        self.worker.progress.connect(lambda v, t: (self.bar.setValue(v), self.lbl_meta.setText(t)))
        self.worker.finished.connect(self.on_done)
        self.worker.start()

    def on_done(self, d):
        self.bar.setVisible(False)
        self.current_duration, self.max_y = d['duration'], d['max_y']
        self.audio_y, self.audio_sr = d['y'], d['sr']
        self.s_norm, self.env_norm = d['s_norm'], d['env_norm']
        
        self.freq_axis.sr, self.freq_axis.max_y, self.freq_axis.is_mel = self.audio_sr, self.max_y, d['is_mel']
        
        for f, l in self.lines:
            if self.freq_axis.is_mel:
                y_pos = (librosa.hz_to_mel(f) / librosa.hz_to_mel(self.audio_sr/2)) * self.max_y
            else:
                y_pos = (f / (self.audio_sr / 2.0)) * self.max_y
            l.setPos(y_pos)
            l.setVisible(f <= (self.audio_sr / 2))
                
        self.loaded = True
        self.apply_theme()
        self.img.setRect(QRectF(0, 0, self.current_duration, self.max_y))
        self.plot.setLimits(xMin=0, xMax=self.current_duration, yMin=0, yMax=self.max_y * 1.05)
        self.mini_img.setRect(QRectF(0, 0, self.current_duration, 100))
        self.mini.setLimits(xMin=0, xMax=self.current_duration, yMin=0, yMax=100)
        
        self.lbl_meta.setText(d['meta'])
        self.playhead.setVisible(True)
        self.mini_ph.setVisible(True)
        self.controls.set_controls_enabled(True)

    def toggle_audio(self):
        if self.is_playing:
            sd.stop()
            self.is_playing = False
            self.timer.stop()
            self.seek_pos += time.time() - self.play_start
        else:
            sd.play(self.audio_y[int(self.seek_pos * self.audio_sr):], self.audio_sr)
            self.play_start = time.time()
            self.is_playing = True
            self.timer.start(cfg.TIMER_INTERVAL_MS)
        self.controls.set_play_text(self.is_playing)

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
            self.toggle_audio()
            self.seek(0)
        else:
            self.playhead.setPos(t)
            self.mini_ph.setPos(t)

    def reset_zoom(self):
        if self.loaded:
            self.plot.autoRange()
            self.plot.setXRange(0, self.current_duration, padding=0)
            self.plot.setYRange(0, self.max_y * 1.05, padding=0)

    def seek_from_click(self, x):
        if self.loaded: self.seek(max(0, min(x, self.current_duration)))

    def on_mouse(self, e):
        if not self.loaded: return
        p = e[0]
        if self.plot.sceneBoundingRect().contains(p):
            mp = self.plot.vb.mapSceneToView(p)
            if 0 <= mp.x() <= self.current_duration and 0 <= mp.y() <= self.max_y:
                self.vL.setVisible(True); self.hL.setVisible(True); self.cursor_label.setVisible(True)
                self.vL.setPos(mp.x()); self.hL.setPos(mp.y())
                hz = (librosa.mel_to_hz((mp.y()/self.max_y)*librosa.hz_to_mel(self.audio_sr/2)) if self.freq_axis.is_mel 
                      else (mp.y()/self.max_y)*(self.audio_sr/2))
                self.cursor_label.setText(f"Time: {int(mp.x()//60)}:{int(mp.x()%60):02d}.{int((mp.x()%1)*1000):03d}\nFreq: {hz/1000:.1f} kHz")
                self.cursor_label.setPos(mp.x(), mp.y())
                self.cursor_label.setAnchor((1.1, 1.1))
            else:
                self.vL.setVisible(False); self.hL.setVisible(False); self.cursor_label.setVisible(False)

    def clear_graph(self):
        sd.stop(); self.is_playing = False; self.timer.stop(); self.img.clear(); self.mini_img.clear(); self.loaded = False
        self.bar.setVisible(False); self.playhead.setVisible(False); self.mini_ph.setVisible(False)
        self.lbl_meta.setText("Drop audio file here to begin...")
        for _, l in self.lines: l.setVisible(False)
        self.controls.set_controls_enabled(False)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        path = e.mimeData().urls()[0].toLocalFile()
        if path.lower().endswith(cfg.SUPPORTED_AUDIO_FORMATS):
            self.load_audio(path, self.controls.get_is_mel())
            
    def keyPressEvent(self, e):
        if self.loaded:
            if e.key() == Qt.Key.Key_Space: self.toggle_audio()
            elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_A): self.seek(self.seek_pos - 5.0)
            elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_D): self.seek(self.seek_pos + 5.0)