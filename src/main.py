import sys
import pyqtgraph as pg
import scipy.fft
import pyfftw
from PyQt6.QtWidgets import QApplication

# Internal modular imports
from ui.main_window import SpectrumAnalyzerApp
from utils.logger import log

# global hardware acceleration for your Ryzen 5 3600
pg.setConfigOptions(antialias=False) 
scipy.fft.set_global_backend(pyfftw.interfaces.scipy_fft)
pyfftw.interfaces.cache.enable()

def main():
    log.info("Starting Spectrum Analyzer Pro...")
    
    app = QApplication(sys.argv)
    window = SpectrumAnalyzerApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()