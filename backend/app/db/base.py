"""
Database Base Configuration

This module provides the SQLAlchemy declarative base and common
mixins for all database models.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import as_declarative, declared_attr
import re


@as_declarative()
class Base:
    """
    Base class for all SQLAlchemy models.
    Provides common functionality and attributes for all models.
    """
    
    id: Any
    __name__: str
    
    # Generate __tablename__ automatically from class name
    @declared_attr
    def __tablename__(cls) -> str:
        """
        Automatically generate table name from class name.
        Example: UserModel -> user_model
        """
        # Convert CamelCase to snake_case
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        return name


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamp fields to models.
    """
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Timestamp when the record was created"
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Timestamp when the record was last updated"
    )


class SoftDeleteMixin:
    """
    Mixin to add soft delete functionality to models.
    Instead of actually deleting records, we mark them as deleted.
    """
    
    deleted_at = Column(
        DateTime,
        nullable=True,
        default=None,
        comment="Timestamp when the record was soft deleted"
    )
    
    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted"""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Soft delete the record"""
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        """Restore a soft deleted record"""
        self.deleted_at = None


# Export all base classes and mixins
__all__ = [
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin"
]

