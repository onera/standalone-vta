"""Console logging configuration for the training command-line entry point."""

import logging


def configure_logging() -> None:
    """Configures package logs without changing third-party logging handlers.

    Repeated calls replace this package's console handler. Library callers can
    instead configure standard Python logging themselves.
    """
    logger = logging.getLogger("src.training")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("{levelname:<7} {message}", style="{"))
    for existing in logger.handlers[:]:
        logger.removeHandler(existing)
        existing.close()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
