"""
Logging configuration for the application.
Uses structured JSON logging for production and colored console logging for development.
"""
import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""

    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(asctime)s %(levelname)s" + reset + " - %(message)s",
        logging.INFO: blue + "%(asctime)s %(levelname)s" + reset + " - %(message)s",
        logging.WARNING: yellow + "%(asctime)s %(levelname)s" + reset + " - %(message)s",
        logging.ERROR: red + "%(asctime)s %(levelname)s" + reset + " - %(message)s",
        logging.CRITICAL: bold_red + "%(asctime)s %(levelname)s" + reset + " - %(message)s",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        # Add milliseconds manually
        result = formatter.format(record)
        # Insert milliseconds after the seconds
        import datetime
        dt = datetime.datetime.fromtimestamp(record.created)
        ms = f".{int((record.created % 1) * 1000):03d}"
        # Replace first occurrence of time format with time+ms
        result = result.replace(dt.strftime("%H:%M:%S"), dt.strftime("%H:%M:%S") + ms, 1)
        return result


def setup_logging() -> None:
    """
    Configure logging for the application.
    Uses JSON logging in production and colored console logging in development.
    """
    log_level = getattr(logging, settings.log_level.upper())

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Use JSON formatter in production, colored formatter in development
    if settings.debug:
        formatter = ColoredFormatter()
    else:
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set logging levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
