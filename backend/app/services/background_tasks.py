"""
Background Task Utilities

Handles long-running tasks using FastAPI BackgroundTasks
"""

from datetime import datetime
from typing import Callable, Any
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
import logging
import traceback

logger = logging.getLogger(__name__)


def run_with_db_session(func: Callable, *args, **kwargs) -> Any:
    """
    Execute function with database session management.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    db = SessionLocal()
    try:
        return func(*args, db=db, **kwargs)
    except Exception as e:
        logger.error(f"Background task failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        db.close()


def safe_background_task(func: Callable):
    """
    Decorator for safe background task execution with error handling.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        try:
            logger.info(f"Starting background task: {func.__name__}")
            result = func(*args, **kwargs)
            logger.info(f"Completed background task: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Background task {func.__name__} failed: {str(e)}")
            logger.error(traceback.format_exc())
    
    return wrapper
