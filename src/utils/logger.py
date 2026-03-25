import logging
import os
from datetime import datetime

def setup_logger():
    """
    Configures a dual-output logger: 
    1. Terminal (for real-time debugging)
    2. File (for permanent error records)
    """
    # Create a logs directory in the project root if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Generate filename based on today's date
    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y-%m-%d')}.log")

    # Define the format: [Timestamp] [Level] [Message]
    log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Root logger setup
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 1. File Handler (appends to the log file)
    fh = logging.FileHandler(log_file)
    fh.setFormatter(log_format)
    logger.addHandler(fh)

    # 2. Console Handler (prints to terminal)
    ch = logging.StreamHandler()
    ch.setFormatter(log_format)
    logger.addHandler(ch)

    return logger

# Initialize a global instance
log = setup_logger()