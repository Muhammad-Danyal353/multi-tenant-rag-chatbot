import logging
import sys
from logging.config import dictConfig
from app.config import settings

def setup_logging():
    """Setup logging configuration."""
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "level": settings.LOG_LEVEL,
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": sys.__stdout__,
            },
        },
        "loggers": {
            "app": {
                "handlers": ["default"],
                "level": settings.LOG_LEVEL,
                "propagate": False,
            },
            # "uvicorn": {
            #     "handlers": ["default"],
            #     "level": settings.LOG_LEVEL,
            #     "propagate": False,
            # },
        },
        "root": {
            "handlers": ["default"],
            "level": settings.LOG_LEVEL,
        }
    }
    
    dictConfig(log_config)
    logging.raiseExceptions = False
