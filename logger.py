import logging
from rich.logging import RichHandler

def setup_logger():
    FORMAT = "%(levelname)s: %(asctime)s \t%(message)s"
    logging.basicConfig(
        level="INFO",
        format=FORMAT,
        handlers=[RichHandler()]
    )
    return logging.getLogger("rich")

logger = setup_logger()
