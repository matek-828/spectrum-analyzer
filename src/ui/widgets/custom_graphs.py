import pyqtgraph as pg
import librosa
from PyQt6.QtCore import pyqtSignal, Qt

# Import our global settings
import config.settings as cfg

class CustomViewBox(pg.ViewBox):
    sigResetZoom = pyqtSignal()
    sigLeftClick = pyqtSignal(float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMenuEnabled(False) 
        self.setMouseMode(self.RectMode)

        self.rbScaleBox.setPen(pg.mkPen(cfg.TEXT_COLOR, width=2))
        self.rbScaleBox.setBrush(pg.mkBrush(255, 255, 255, 40))

        self.zoom_text = pg.TextItem("Zoom", color=cfg.TEXT_COLOR, anchor=(0, 0))
        self.zoom_text.setZValue(1000)
        self.addItem(self.zoom_text, ignoreBounds=True)
        self.zoom_text.setVisible(False)

    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
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
            
            if ev.isStart():
                self.zoom_text.setVisible(True)
            
            if ev.isFinish():
                self.zoom_text.setVisible(False)
            else:
                pos = self.mapSceneToView(ev.scenePos())
                view_range = self.viewRange()[0]
                offset = (view_range[1] - view_range[0]) * 0.01
                self.zoom_text.setPos(pos.x() + offset, pos.y())

            orig_btn = ev.button
            orig_bdp = ev.buttonDownPos
            orig_bdsp = ev.buttonDownScenePos
            orig_bdscp = ev.buttonDownScreenPos

            ev.button = lambda: Qt.MouseButton.LeftButton
            ev.buttonDownPos = lambda btn=None: orig_bdp(Qt.MouseButton.RightButton) if btn in (Qt.MouseButton.LeftButton, None) else orig_bdp(btn)
            ev.buttonDownScenePos = lambda btn=None: orig_bdsp(Qt.MouseButton.RightButton) if btn in (Qt.MouseButton.LeftButton, None) else orig_bdsp(btn)
            ev.buttonDownScreenPos = lambda btn=None: orig_bdscp(Qt.MouseButton.RightButton) if btn in (Qt.MouseButton.LeftButton, None) else orig_bdscp(btn)

            super().mouseDragEvent(ev, axis)

            ev.button = orig_btn
            ev.buttonDownPos = orig_bdp
            ev.buttonDownScenePos = orig_bdsp
            ev.buttonDownScreenPos = orig_bdscp

        elif ev.button() == Qt.MouseButton.MiddleButton:
            ev.accept()
            p1 = self.mapToView(ev.pos())
            p2 = self.mapToView(ev.lastPos())
            self.translateBy(x=p2.x() - p1.x(), y=p2.y() - p1.y())
        else:
            ev.ignore()


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
        # Look to our global settings for the tick marks
        self.target_hz = cfg.TARGET_HZ_TICKS 

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