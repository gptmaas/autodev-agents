"""Structured logging configuration for the multi-agent system."""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str = "autodev",
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_colors: bool = True
) -> logging.Logger:
    """Set up a structured logger for the application.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        use_colors: Whether to use colored output for console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logger.level)

    # Format: timestamp [level] [session_id] message
    log_format = "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    if use_colors:
        console_formatter = ColoredFormatter(log_format, datefmt=date_format)
    else:
        console_formatter = logging.Formatter(log_format, datefmt=date_format)

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logger.level)
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_session_logger(session_id: str) -> logging.Logger:
    """Get a logger with session-specific context.

    Args:
        session_id: Session identifier

    Returns:
        Logger with session context
    """
    logger = logging.getLogger(f"autodev.{session_id}")
    return logger


class LoggerContext:
    """Context manager for temporary log level changes."""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.new_level = level
        self.old_level = None

    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.setLevel(self.new_level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.old_level)


# Global logger instance
_global_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """Get the global logger instance.

    Returns:
        Global logger (creates one if doesn't exist)
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = setup_logger()
    return _global_logger
