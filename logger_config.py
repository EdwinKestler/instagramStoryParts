import logging

def get_logger(name: str = __name__) -> logging.Logger:
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s - %(levelname)s - %(message)s")
    return logging.getLogger(name)
