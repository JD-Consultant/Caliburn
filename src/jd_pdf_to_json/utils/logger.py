"""Logging utility."""

import sys
from loguru import logger

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

__all__ = ["logger"]
