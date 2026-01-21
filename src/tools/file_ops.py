"""File operations for the multi-agent system."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from ..utils.helpers import ensure_directory
from ..config.settings import get_settings


logger = get_logger()


def read_file(file_path: str | Path, encoding: str = "utf-8") -> str:
    """Read a file and return its content.

    Args:
        file_path: Path to the file
        encoding: File encoding (default: utf-8)

    Returns:
        File content as string

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        content = path.read_text(encoding=encoding)
        logger.debug(f"Read file: {file_path} ({len(content)} bytes)")
        return content
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


def write_file(file_path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Path to the file
        content: Content to write
        encoding: File encoding (default: utf-8)

    Raises:
        IOError: If file cannot be written
    """
    path = Path(file_path)
    ensure_directory(path.parent)

    try:
        path.write_text(content, encoding=encoding)
        logger.debug(f"Wrote file: {file_path} ({len(content)} bytes)")
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        raise


def append_file(file_path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """Append content to a file.

    Args:
        file_path: Path to the file
        content: Content to append
        encoding: File encoding (default: utf-8)
    """
    path = Path(file_path)
    try:
        with path.open("a", encoding=encoding) as f:
            f.write(content)
        logger.debug(f"Appended to file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to append to file {file_path}: {e}")
        raise


def file_exists(file_path: str | Path) -> bool:
    """Check if a file exists.

    Args:
        file_path: Path to check

    Returns:
        True if file exists, False otherwise
    """
    return Path(file_path).exists()


def list_files(directory: str | Path, pattern: str = "*", recursive: bool = False) -> List[Path]:
    """List files in a directory.

    Args:
        directory: Directory path
        pattern: Glob pattern to match
        recursive: Whether to search recursively

    Returns:
        List of file paths
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    if recursive:
        return list(dir_path.rglob(pattern))
    return list(dir_path.glob(pattern))


def parse_markdown_sections(markdown: str) -> Dict[str, str]:
    """Parse markdown content into sections.

    Args:
        markdown: Markdown content

    Returns:
        Dictionary mapping section titles to content
    """
    sections: Dict[str, str] = {}
    current_section = "introduction"
    current_content: List[str] = []

    lines = markdown.split("\n")
    for line in lines:
        # Check for heading (## or ###)
        heading_match = re.match(r"^#{2,3}\s+(.+)", line)
        if heading_match:
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()
                current_content = []

            # Start new section
            current_section = heading_match.group(1).strip().lower().replace(" ", "_")
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def extract_markdown_section(markdown: str, section_title: str) -> Optional[str]:
    """Extract a specific section from markdown content.

    Args:
        markdown: Markdown content
        section_title: Title of the section to extract

    Returns:
        Section content or None if not found
    """
    sections = parse_markdown_sections(markdown)
    section_key = section_title.lower().replace(" ", "_")
    return sections.get(section_key)


def parse_tasks_json(file_path: str | Path) -> List[Dict[str, Any]]:
    """Parse tasks.json file and return task list.

    Args:
        file_path: Path to tasks.json

    Returns:
        List of task dictionaries

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    content = read_file(file_path)
    tasks = json.loads(content)

    if not isinstance(tasks, list):
        raise ValueError("tasks.json must contain a list of tasks")

    # Validate task structure
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task must be a dictionary")
        if "id" not in task:
            raise ValueError("Each task must have an 'id' field")
        if "title" not in task:
            raise ValueError("Each task must have a 'title' field")

    logger.info(f"Loaded {len(tasks)} tasks from {file_path}")
    return tasks


def write_tasks_json(file_path: str | Path, tasks: List[Dict[str, Any]]) -> None:
    """Write task list to tasks.json file.

    Args:
        file_path: Path to tasks.json
        tasks: List of task dictionaries
    """
    # Validate tasks before writing
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each task must be a dictionary")
        if "id" not in task or "title" not in task:
            raise ValueError("Each task must have 'id' and 'title' fields")

    content = json.dumps(tasks, indent=2)
    write_file(file_path, content)
    logger.info(f"Wrote {len(tasks)} tasks to {file_path}")


def parse_markdown_code_blocks(markdown: str, language: Optional[str] = None) -> List[Tuple[str, str]]:
    """Extract code blocks from markdown content.

    Args:
        markdown: Markdown content
        language: Optional language filter (e.g., "python", "javascript")

    Returns:
        List of (language, code) tuples
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, markdown, re.DOTALL)

    if language:
        return [(lang, code) for lang, code in matches if lang.lower() == language.lower()]
    return matches


def get_task_by_id(tasks: List[Dict[str, Any]], task_id: str) -> Optional[Dict[str, Any]]:
    """Find a task by its ID.

    Args:
        tasks: List of task dictionaries
        task_id: Task ID to find

    Returns:
        Task dictionary or None if not found
    """
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def get_ready_tasks(tasks: List[Dict[str, Any]], completed: List[str]) -> List[Dict[str, Any]]:
    """Get tasks that are ready to be executed (no pending dependencies).

    Args:
        tasks: List of task dictionaries
        completed: List of completed task IDs

    Returns:
        List of tasks ready for execution
    """
    ready = []
    completed_set = set(completed)

    for task in tasks:
        # Skip already completed tasks
        if task["id"] in completed_set:
            continue

        # Skip tasks with status "completed"
        if task.get("status") == "completed":
            continue

        # Check if all dependencies are satisfied
        dependencies = task.get("dependencies", [])
        if all(dep in completed_set for dep in dependencies):
            ready.append(task)

    return ready


def validate_json_structure(data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate JSON data against a simple schema.

    Args:
        data: Data to validate
        schema: Schema definition (simple type checking)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"

    for key, expected_type in schema.items():
        if key not in data:
            return False, f"Missing required key: {key}"

        value = data[key]
        if expected_type == "list" and not isinstance(value, list):
            return False, f"Key '{key}' must be a list"
        elif expected_type == "dict" and not isinstance(value, dict):
            return False, f"Key '{key}' must be a dictionary"
        elif expected_type == "str" and not isinstance(value, str):
            return False, f"Key '{key}' must be a string"
        elif expected_type == "int" and not isinstance(value, int):
            return False, f"Key '{key}' must be an integer"

    return True, None


def create_session_artifact(workspace: Path, artifact_type: str, filename: str, content: str) -> Path:
    """Create an artifact file in the session workspace.

    Args:
        workspace: Session workspace directory
        artifact_type: Type of artifact (prd, design, code, etc.)
        filename: Name of the file
        content: File content

    Returns:
        Path to created file
    """
    artifact_dir = workspace / artifact_type
    artifact_dir = ensure_directory(artifact_dir)

    file_path = artifact_dir / filename
    write_file(file_path, content)
    return file_path


def load_session_artifact(workspace: Path, artifact_type: str, filename: str) -> str:
    """Load an artifact file from the session workspace.

    Args:
        workspace: Session workspace directory
        artifact_type: Type of artifact (prd, design, code, etc.)
        filename: Name of the file

    Returns:
        File content

    Raises:
        FileNotFoundError: If artifact doesn't exist
    """
    artifact_path = workspace / artifact_type / filename
    return read_file(artifact_path)


def update_tasks_json_file(session_id: str, task_list: List[Dict[str, Any]]) -> None:
    """Update tasks.json with current task statuses.

    This function writes the current task_list to the tasks.json file
    in the session workspace, ensuring that task status changes are
    persisted to disk.

    Args:
        session_id: Session identifier
        task_list: Current list of tasks with updated statuses
    """
    settings = get_settings()
    workspace = settings.get_session_workspace(session_id)
    tasks_path = workspace / "tasks.json"
    write_tasks_json(tasks_path, task_list)
    logger.info(f"Updated tasks.json for session {session_id} with {len(task_list)} tasks")
