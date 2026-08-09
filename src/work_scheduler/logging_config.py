import logging

LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging to stderr."""
    logging.basicConfig(level=level, format=LOG_FORMAT)
