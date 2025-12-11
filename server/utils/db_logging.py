"""
Database modification logging utility.

Logs all database INSERT, UPDATE, and DELETE operations to a file
in YAML format for audit and debugging purposes.
"""

import logging
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler


class DatabaseModificationLogger:
    """Logger for database modifications with YAML output format."""

    def __init__(
        self,
        log_file_path: str | Path,
        log_level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """
        Initialize the database modification logger.

        Args:
            log_file_path: Path to the log file
            log_level: Logging level (default: INFO)
            max_bytes: Maximum log file size before rotation (default: 10MB)
            backup_count: Number of backup log files to keep (default: 5)
        """
        self.log_file_path = Path(log_file_path)

        # Ensure log directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("eyened.db_modifications")
        self.logger.setLevel(log_level)

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Create rotating file handler
        handler = RotatingFileHandler(
            self.log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(log_level)

        # Use a custom formatter that outputs YAML
        handler.setFormatter(YAMLFormatter())

        self.logger.addHandler(handler)
        self.logger.propagate = False  # Don't propagate to root logger

    def log_insert(
        self,
        user: str,
        user_id: int,
        endpoint: str,
        entity: str,
        entity_id: Optional[int | str] = None,
        fields: Optional[Dict[str, Any]] = None,
        summary: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ):
        """
        Log an INSERT operation.

        Args:
            user: Username who performed the operation
            user_id: User ID who performed the operation
            endpoint: API endpoint (e.g., "POST /api/tags")
            entity: Entity type (e.g., "Tag", "Task")
            entity_id: ID of the created entity (optional)
            fields: Dictionary of fields that were set (optional)
            summary: Summary statistics for bulk operations (optional)
            status: Operation status (default: "success")
        """
        self._log_operation(
            operation="INSERT",
            user=user,
            user_id=user_id,
            endpoint=endpoint,
            entity=entity,
            entity_id=entity_id,
            fields=fields,
            summary=summary,
            status=status,
        )

    def log_update(
        self,
        user: str,
        user_id: int,
        endpoint: str,
        entity: str,
        entity_id: Optional[int | str] = None,
        fields: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ):
        """
        Log an UPDATE operation.

        Args:
            user: Username who performed the operation
            user_id: User ID who performed the operation
            endpoint: API endpoint (e.g., "PATCH /api/tags/42")
            entity: Entity type (e.g., "Tag", "Task")
            entity_id: ID of the updated entity (optional for link entities)
            fields: Dictionary of identifying fields for link entities (optional)
            changes: Dictionary of changed fields with old->new values (optional)
            status: Operation status (default: "success")
        """
        self._log_operation(
            operation="UPDATE",
            user=user,
            user_id=user_id,
            endpoint=endpoint,
            entity=entity,
            entity_id=entity_id,
            fields=fields,
            changes=changes,
            status=status,
        )

    def log_delete(
        self,
        user: str,
        user_id: int,
        endpoint: str,
        entity: str,
        entity_id: Optional[int | str] = None,
        fields: Optional[Dict[str, Any]] = None,
        deleted_data: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ):
        """
        Log a DELETE operation.

        Args:
            user: Username who performed the operation
            user_id: User ID who performed the operation
            endpoint: API endpoint (e.g., "DELETE /api/tags/42")
            entity: Entity type (e.g., "Tag", "Task")
            entity_id: ID of the deleted entity (optional for link entities)
            fields: Dictionary of identifying fields for link entities (optional)
            deleted_data: Dictionary of deleted entity data for restoration (optional)
            status: Operation status (default: "success")
        """
        self._log_operation(
            operation="DELETE",
            user=user,
            user_id=user_id,
            endpoint=endpoint,
            entity=entity,
            entity_id=entity_id,
            fields=fields,
            deleted_data=deleted_data,
            status=status,
        )

    def _log_operation(
        self,
        operation: str,
        user: str,
        user_id: int,
        endpoint: str,
        entity: str,
        entity_id: Optional[int | str] = None,
        fields: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        summary: Optional[Dict[str, Any]] = None,
        deleted_data: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ):
        """Internal method to log operations."""
        timestamp = datetime.now(timezone.utc).isoformat()

        log_data = {
            timestamp: {
                "user": user,
                "user_id": user_id,
                "endpoint": endpoint,
                "operation": operation,
                "entity": entity,
            }
        }

        if entity_id is not None:
            log_data[timestamp]["entity_id"] = entity_id

        if fields:
            log_data[timestamp]["fields"] = fields

        if changes:
            log_data[timestamp]["changes"] = changes

        if summary:
            log_data[timestamp]["summary"] = summary

        if deleted_data:
            log_data[timestamp]["deleted_data"] = deleted_data

        log_data[timestamp]["status"] = status

        # Format as YAML and log
        yaml_str = yaml.dump(
            log_data, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        self.logger.info(yaml_str.rstrip())  # Remove trailing newline
    
    def log_simple(
        self,
        user: str,
        user_id: int,
        endpoint: str,
        operation: str,
        entity: str,
        entity_id: Optional[int | str] = None,
        status: str = "success",
    ):
        """
        Log a simple one-line operation (for high-frequency operations).
        
        Args:
            user: Username who performed the operation
            user_id: User ID who performed the operation
            endpoint: API endpoint
            operation: Operation type (INSERT/UPDATE/DELETE)
            entity: Entity type
            entity_id: ID of the entity (optional)
            status: Operation status (default: "success")
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entity_str = f"{entity}:{entity_id}" if entity_id is not None else entity
        log_line = f"{timestamp} [{user}:{user_id}] {endpoint} {operation} {entity_str} {status}"
        self.logger.info(log_line)


class YAMLFormatter(logging.Formatter):
    """Custom formatter that passes through YAML strings without modification."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record."""
        # The message is already formatted as YAML, just return it
        return record.getMessage()


# Global logger instance (will be initialized in main.py)
_db_logger: Optional[DatabaseModificationLogger] = None


def init_db_logger(settings) -> DatabaseModificationLogger:
    """
    Initialize the global database modification logger.

    Args:
        settings: Application settings object

    Returns:
        Initialized DatabaseModificationLogger instance
    """
    global _db_logger

    log_file_path = getattr(
        settings, "db_log_file_path", "/var/log/eyened/db_modifications.log"
    )
    log_level = getattr(settings, "db_log_level", logging.INFO)
    max_bytes = getattr(settings, "db_log_max_bytes", 10 * 1024 * 1024)  # 10MB
    backup_count = getattr(settings, "db_log_backup_count", 5)

    _db_logger = DatabaseModificationLogger(
        log_file_path=log_file_path,
        log_level=log_level,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )

    return _db_logger


def get_db_logger() -> Optional[DatabaseModificationLogger]:
    """Get the global database modification logger instance."""
    return _db_logger
