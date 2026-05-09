import logging
import structlog
from backend.core.config import settings

"""
Structured Json logging setup using structlog 
Every log in Json with timestamp,level message and context
"""

def setup_logging():
    """ Congigured structured logging for the application."""
    log_level = logging.DEBUG if settings.environment == "development" else logging.INFO

    structlog.configure(
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt = "iso"),
            structlog.processors.JSONRenderer()
            if settings.environment == "production"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class= dict,
        logger_factory= structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )

def get_logger(name:str = "intervue"):
    """ Get a structured logger instance"""
    return structlog.get_logger(name)
