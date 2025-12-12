import os
import logging
from logging.handlers import RotatingFileHandler
from config.settings import Settings

def init_logger(settings: Settings):
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = RotatingFileHandler("logs/trade.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger
