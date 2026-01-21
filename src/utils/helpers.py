"""Utility functions for the multi-agent system."""

import os
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


def generate_session_id() -> str:
    """Generate a unique session ID.

    Returns:
        Unique session identifier
    """
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_workspace_path(workspace_root: str, session_id: str) -> Path:
    """Get the workspace path for a session.

    Args:
        workspace_root: Root workspace directory
        session_id: Session identifier

    Returns:
        Path to session workspace
    """
    workspace = ensure_directory(workspace_root)
    session_path = workspace / session_id
    return ensure_directory(session_path)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    return sanitized or "unnamed"


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_code_blocks(text: str, language: Optional[str] = None) -> List[str]:
    """Extract code blocks from markdown text.

    Args:
        text: Markdown text
        language: Optional language filter (e.g., "python", "javascript")

    Returns:
        List of code block contents
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    if language:
        return [code for lang, code in matches if lang.lower() == language.lower()]
    return [code for _, code in matches]


def parse_list(text: str) -> List[str]:
    """Parse a markdown list into a Python list.

    Args:
        text: Markdown list text

    Returns:
        List of items
    """
    items = []
    for line in text.split('\n'):
        line = line.strip()
        # Match - or * bullets
        match = re.match(r'^[\-\*]\s+(.+)', line)
        if match:
            items.append(match.group(1))
            continue
        # Match numbered lists (1., 2., etc.)
        match = re.match(r'^\d+\.\s+(.+)', line)
        if match:
            items.append(match.group(1))
    return items


def safe_get(data: Dict[str, Any], *keys, default: Any = None) -> Any:
    """Safely get nested dictionary values.

    Args:
        data: Dictionary to query
        *keys: Nested keys to traverse
        default: Default value if key not found

    Returns:
        Value at key path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def merge_dicts(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries.

    Args:
        base: Base dictionary
        update: Dictionary to merge into base

    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format a datetime as a string.

    Args:
        dt: Datetime to format (uses current time if None)

    Returns:
        Formatted timestamp string
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def validate_json_path(path: str) -> bool:
    """Validate a JSONPath expression.

    Args:
        path: JSONPath string

    Returns:
        True if valid, False otherwise
    """
    # Basic validation - check for balanced brackets
    open_brackets = path.count('[')
    close_brackets = path.count(']')
    return open_brackets == close_brackets


def get_env_var(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Get an environment variable with optional validation.

    Args:
        name: Environment variable name
        default: Default value if not found
        required: Whether to raise error if not found

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required=True and variable not found
    """
    value = os.getenv(name, default)
    if required and value is None:
        raise ValueError(f"Required environment variable '{name}' is not set")
    return value


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks.

    Args:
        items: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
