"""
Loguru configuration for experiments. Call configure_experiments_logging() at startup
to set level and format. Otherwise use the default logger.
"""
import os
import sys

from loguru import logger


def configure_experiments_logging(
    level: str | None = None,
    sink=sys.stderr,
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
) -> None:
    """Configure loguru for experiments. Level from LOG_LEVEL env or default DEBUG."""
    log_level = (level or os.environ.get("LOG_LEVEL", "DEBUG")).upper()
    logger.remove()
    logger.add(sink, level=log_level, format=format)
    logger.info("Experiments logging configured level={}", log_level)


# Module-level logger for experiments (use this in experiments.* modules)
log = logger
