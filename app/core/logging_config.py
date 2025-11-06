"""
Structured logging configuration for Social Flood API.

This module configures structured JSON logging for better log parsing,
analysis, and integration with log aggregation systems.
"""
import logging
import sys
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds additional context to log messages.
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """
        Add custom fields to the log record.

        Args:
            log_record: The log record dictionary to modify
            record: The original logging.LogRecord object
            message_dict: Additional message context
        """
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name

        # Add request ID if available (set by RequestIDMiddleware)
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id

        # Add user ID if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id

        # Add environment info
        if hasattr(record, 'environment'):
            log_record['environment'] = record.environment


def setup_structured_logging(
    level: str = "INFO",
    log_format: str = "json"
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: The log format ('json' or 'text')
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if log_format.lower() == "json":
        # Use JSON formatter
        formatter = CustomJsonFormatter(
            fmt='%(timestamp)s %(level)s %(logger)s %(message)s',
            rename_fields={
                'timestamp': '@timestamp',
                'level': 'severity',
                'logger': 'logger_name'
            }
        )
    else:
        # Use text formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class RequestLogger:
    """
    Context manager for adding request context to log messages.
    """

    def __init__(self, request_id: str, user_id: str = None):
        """
        Initialize the request logger.

        Args:
            request_id: The unique request identifier
            user_id: The user identifier (optional)
        """
        self.request_id = request_id
        self.user_id = user_id
        self.old_factory = None

    def __enter__(self):
        """Add request context to log records."""
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = self.request_id
            if self.user_id:
                record.user_id = self.user_id
            return record

        logging.setLogRecordFactory(record_factory)
        self.old_factory = old_factory
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original log record factory."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


# Example usage:
# from app.core.logging_config import RequestLogger
#
# async def some_endpoint(request: Request):
#     with RequestLogger(request.state.request_id):
#         logger.info("Processing request", extra={"action": "process"})
