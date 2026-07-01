import logging
import os
from pythonjsonlogger import jsonlogger

LOG_FILE = "/var/log/csye6225/webapp.log"
LOG_DIR = "/var/log/csye6225"


def setup_logger(name: str) -> logging.Logger:
    """
    Returns a JSON-structured logger.
    On EC2: writes to /var/log/csye6225/webapp.log (CloudWatch agent reads this)
    Locally: writes to stdout only
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Check handler types to avoid duplicates on repeated imports
    has_stream = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    has_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    if not has_stream:
        stdout_handler = logging.StreamHandler()
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

    if not has_file:
        # Try to open the file directly — no os.access() check
        # os.access() checks the process owner at import time which can be
        # unreliable inside systemd with ProtectSystem=strict
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            file_handler = logging.FileHandler(LOG_FILE)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError):
            # Running locally without /var/log/csye6225 — stdout only is fine
            pass

    return logger
