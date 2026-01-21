"""Checkpoint management for LangGraph workflow persistence."""

import sqlite3
from pathlib import Path
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import ensure_directory


logger = get_logger()


class CheckpointManager:
    """Manager for LangGraph checkpointing.

    Handles checkpoint backend selection and initialization.
    """

    def __init__(self, backend: Optional[str] = None):
        """Initialize the checkpoint manager.

        Args:
            backend: Checkpoint backend ("memory" or "sqlite")
                    Defaults to settings value
        """
        settings = get_settings()
        self.backend = backend or settings.agent.checkpoint_backend
        self.checkpointer = self._create_checkpointer()

        logger.info(f"Initialized checkpoint manager with backend: {self.backend}")

    def _create_checkpointer(self):
        """Create the checkpointer instance.

        Returns:
            Checkpointer instance
        """
        if self.backend == "sqlite":
            return self._create_sqlite_checkpointer()
        else:
            # Default to memory
            if self.backend != "memory":
                logger.warning(f"Checkpoint backend '{self.backend}' not supported, using 'memory'")
            return MemorySaver()

    def _create_sqlite_checkpointer(self) -> SqliteSaver:
        """Create an SQLite checkpointer.

        Returns:
            SqliteSaver instance
        """
        settings = get_settings()

        # Create checkpoints directory
        workspace = Path(settings.workspace.root)
        checkpoints_dir = ensure_directory(workspace / "checkpoints")

        # Database path
        db_path = checkpoints_dir / "checkpoints.db"

        logger.info(f"Using SQLite checkpoint database: {db_path}")

        # Create SQLite connection with check_same_thread=False
        # This is needed because LangGraph may access the connection from different threads
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        return SqliteSaver(conn)

    def get_checkpointer(self):
        """Get the checkpointer instance.

        Returns:
            Checkpointer instance
        """
        return self.checkpointer

    def get_checkpoint_path(self, session_id: str) -> Path:
        """Get the path for a session's checkpoint data.

        Args:
            session_id: Session identifier

        Returns:
            Path to checkpoint directory
        """
        settings = get_settings()
        workspace = Path(settings.workspace.root)
        checkpoints_dir = ensure_directory(workspace / "checkpoints")
        return checkpoints_dir / session_id


# Global checkpoint manager instance
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager(backend: Optional[str] = None) -> CheckpointManager:
    """Get the global checkpoint manager instance.

    Args:
        backend: Optional backend override

    Returns:
        CheckpointManager instance
    """
    global _checkpoint_manager
    if _checkpoint_manager is None or backend is not None:
        _checkpoint_manager = CheckpointManager(backend)
    return _checkpoint_manager


def get_checkpointer():
    """Get the checkpointer for use with LangGraph.

    Returns:
        Checkpointer instance
    """
    return get_checkpoint_manager().get_checkpointer()


def reset_checkpoint_manager() -> None:
    """Reset the global checkpoint manager (useful for testing)."""
    global _checkpoint_manager
    _checkpoint_manager = None
