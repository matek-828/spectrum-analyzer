from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QComboBox
from PyQt6.QtCore import pyqtSignal

class ControlBar(QWidget):
    # Define custom signals to communicate with the Main Window seamlessly
    sig_play = pyqtSignal()
    sig_scale = pyqtSignal()
    sig_theme = pyqtSignal(str)
    sig_export = pyqtSignal()
    sig_clear = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch() 

        # Play Button
        self.btn_p = QPushButton("Play (Space)")
        self.btn_p.clicked.connect(self.sig_play.emit)

        # Scale Button
        self.btn_scale = QPushButton("Scale: Linear")
        self.btn_scale.clicked.connect(self.sig_scale.emit)

        # Theme Combo Box
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Theme: DJ", "Theme: Cyberpunk", "Theme: Red", "Theme: Green", "Theme: Blue", "Theme: Monochrome"])
        self.combo_theme.currentTextChanged.connect(self.sig_theme.emit)

        # NEW: The Export Button
        self.btn_export = QPushButton("Export Snippet")
        self.btn_export.clicked.connect(self.sig_export.emit)

        # Clear Button
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.sig_clear.emit)

        # Apply styling and add to layout dynamically
        for w in [self.btn_p, self.btn_scale, self.combo_theme, self.btn_export, self.btn_clear]:
            w.setEnabled(False)
            if isinstance(w, QComboBox):
                w.setFixedSize(180, 30)
                w.setStyleSheet("""
                    QComboBox { background-color: #333; color: white; border: 1px solid #555; border-radius: 4px; padding-left: 8px; } 
                    QComboBox::drop-down { border: none; } 
                    QComboBox QAbstractItemView { background-color: #333; color: white; selection-background-color: #0078d7; }
                """)
            else:
                w.setFixedSize(130, 30)
                w.setStyleSheet("QPushButton { background-color: #333; color: white; border-radius: 4px; padding: 5px; }")
            layout.addWidget(w)

        layout.addStretch()

    # --- Helper Methods for the Main Window ---
    def set_controls_enabled(self, state):
        """Easily toggle all buttons on or off at once."""
        self.btn_p.setEnabled(state)
        self.btn_scale.setEnabled(state)
        self.combo_theme.setEnabled(state)
        self.btn_export.setEnabled(state)
        self.btn_clear.setEnabled(state)

    def set_play_text(self, is_playing):
        self.btn_p.setText("Pause (Space)" if is_playing else "Play (Space)")
        
    def toggle_scale_text(self):
        """Swaps text and returns True if Mel is now active."""
        use_mel = ("Linear" in self.btn_scale.text())
        self.btn_scale.setText("Scale: Mel" if use_mel else "Scale: Linear")
        return use_mel
    
    def get_current_theme(self):
        return self.combo_theme.currentText()
    
    def get_is_mel(self):
        return "Mel" in self.btn_scale.text()