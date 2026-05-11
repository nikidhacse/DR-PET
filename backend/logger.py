import logging
import sys
import os

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler for permanent monitoring
        os.makedirs("data/logs", exist_ok=True)
        fh = logging.FileHandler('data/logs/dr_pet.log')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
