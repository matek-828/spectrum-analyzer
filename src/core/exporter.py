import soundfile as sf
from PyQt6.QtCore import QThread, pyqtSignal

class ExportWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, audio_y, sr, start_time, end_time, output_path):
        super().__init__()
        self.audio_y = audio_y
        self.sr = sr
        self.start_time = start_time
        self.end_time = end_time
        self.output_path = output_path

    def run(self):
        try:
            # convert seconds to exact array indices
            start_sample = int(self.start_time * self.sr)
            end_sample = int(self.end_time * self.sr)

            # clamp to safe bounds
            start_sample = max(0, start_sample)
            end_sample = min(len(self.audio_y), end_sample)

            if start_sample >= end_sample:
                raise ValueError("Export duration must be greater than zero.")

            # slice the high-res audio array
            audio_slice = self.audio_y[start_sample:end_sample]

            # write the new file to disk
            sf.write(self.output_path, audio_slice, self.sr)

            # signal UI that it finished successfully
            self.finished.emit(self.output_path)
            
        except Exception as e:
            self.error.emit(str(e))