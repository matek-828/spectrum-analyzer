from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QDoubleSpinBox, 
                             QLineEdit, QFileDialog, QMessageBox)

class ExportDialog(QDialog):
    def __init__(self, max_duration, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Audio Snippet")
        self.setFixedSize(400, 180)
        self.setStyleSheet("QDialog { background-color: #1e1e1e; color: white; } QLabel { color: white; }")
        
        self.max_duration = max_duration
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # time selection (accurate to milliseconds)
        time_layout = QHBoxLayout()
        
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(0, self.max_duration)
        self.spin_start.setDecimals(3)
        self.spin_start.setSuffix(" s")
        
        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(0, self.max_duration)
        self.spin_end.setValue(self.max_duration)
        self.spin_end.setDecimals(3)
        self.spin_end.setSuffix(" s")

        time_layout.addWidget(QLabel("Start Time:"))
        time_layout.addWidget(self.spin_start)
        time_layout.addWidget(QLabel("End Time:"))
        time_layout.addWidget(self.spin_end)
        
        layout.addLayout(time_layout)

        # file path selection
        path_layout = QHBoxLayout()
        self.txt_path = QLineEdit()
        self.txt_path.setReadOnly(True)
        self.txt_path.setPlaceholderText("Select save destination...")
        
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_path)
        
        path_layout.addWidget(self.txt_path)
        path_layout.addWidget(self.btn_browse)
        
        layout.addWidget(QLabel("Save to:"))
        layout.addLayout(path_layout)

        # action buttons
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export Lossless")
        self.btn_export.clicked.connect(self.validate_and_accept)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_export)
        
        layout.addLayout(btn_layout)

        # styling
        for btn in [self.btn_browse, self.btn_export, self.btn_cancel]:
            btn.setStyleSheet("background-color: #333; color: white; padding: 6px; border-radius: 4px;")
            
        for box in [self.txt_path, self.spin_start, self.spin_end]:
            box.setStyleSheet("background-color: #2a2a2a; color: white; border: 1px solid #555; padding: 4px;")

    def browse_path(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Audio", "", "WAV Files (*.wav)")
        if path:
            self.txt_path.setText(path)

    def validate_and_accept(self):
        if self.spin_start.value() >= self.spin_end.value():
            QMessageBox.warning(self, "Invalid Time", "Start time must be before end time.")
            return
            
        if not self.txt_path.text():
            QMessageBox.warning(self, "Missing Path", "Please select a save destination.")
            return
            
        self.accept()

    def get_export_params(self):
        return self.spin_start.value(), self.spin_end.value(), self.txt_path.text()