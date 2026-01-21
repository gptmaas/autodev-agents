"""Output validators for the multi-agent system."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from ..utils.logger import get_logger


logger = get_logger()


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


def validate_prd(content: str) -> Tuple[bool, List[str]]:
    """Validate PRD content.

    Checks that PRD contains expected sections and structure.

    Args:
        content: PRD markdown content

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check for required sections
    required_sections = [
        "overview", "user stories", "functional requirements",
        "non-functional requirements", "success metrics"
    ]

    content_lower = content.lower()
    for section in required_sections:
        if section not in content_lower:
            errors.append(f"Missing required section: {section}")

    # Check for user stories format
    user_story_pattern = r"as a\s+.+?\s+i want\s+.+?\s+so that"
    if not re.search(user_story_pattern, content_lower):
        errors.append("No properly formatted user stories found (As a... I want... so that...)")

    # Check minimum length
    if len(content) < 500:
        errors.append("PRD content is too short (less than 500 characters)")

    # Check for acceptance criteria
    if "acceptance criteria" not in content_lower:
        errors.append("Missing acceptance criteria for features")

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"PRD validation failed: {errors}")
    else:
        logger.info("PRD validation passed")

    return is_valid, errors


def validate_design(content: str) -> Tuple[bool, List[str]]:
    """Validate design document content.

    Checks that design document contains expected sections.

    Args:
        content: Design markdown content

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check for required sections
    required_sections = [
        "architecture overview", "system design",
        "file structure", "implementation approach"
    ]

    content_lower = content.lower()
    for section in required_sections:
        if section not in content_lower:
            errors.append(f"Missing required section: {section}")

    # Check for technology stack
    if "technology stack" not in content_lower and "tech stack" not in content_lower:
        errors.append("Missing technology stack information")

    # Check for data models
    if "data model" not in content_lower:
        errors.append("Missing data models section")

    # Check minimum length
    if len(content) < 800:
        errors.append("Design content is too short (less than 800 characters)")

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Design validation failed: {errors}")
    else:
        logger.info("Design validation passed")

    return is_valid, errors


def validate_tasks(tasks: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate task list structure.

    Args:
        tasks: List of task dictionaries

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not tasks:
        errors.append("Task list is empty")
        return False, errors

    # Validate each task
    task_ids = set()
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"Task {i}: Not a dictionary")
            continue

        # Required fields
        required_fields = ["id", "title", "description", "status"]
        for field in required_fields:
            if field not in task:
                errors.append(f"Task {i}: Missing required field '{field}'")

        # Validate ID
        if "id" in task:
            task_id = task["id"]
            if task_id in task_ids:
                errors.append(f"Task {i}: Duplicate ID '{task_id}'")
            task_ids.add(task_id)

        # Validate status
        if "status" in task:
            valid_statuses = ["pending", "in_progress", "completed", "blocked"]
            if task["status"] not in valid_statuses:
                errors.append(f"Task {i}: Invalid status '{task['status']}'")

        # Validate dependencies exist
        if "dependencies" in task:
            deps = task["dependencies"]
            if not isinstance(deps, list):
                errors.append(f"Task {i}: Dependencies must be a list")
            else:
                for dep in deps:
                    if dep not in task_ids and dep != task.get("id"):
                        # Dependency might be a later task, so we'll check later
                        pass

        # Validate priority
        if "priority" in task:
            priority = task["priority"]
            if not isinstance(priority, (int, float)) or priority < 1 or priority > 10:
                errors.append(f"Task {i}: Priority must be between 1 and 10")

    # Second pass: validate all dependencies exist
    task_ids = {task.get("id") for task in tasks if "id" in task}
    for i, task in enumerate(tasks):
        if "dependencies" in task and isinstance(task["dependencies"], list):
            for dep in task["dependencies"]:
                if dep not in task_ids:
                    errors.append(f"Task {i}: Dependency '{dep}' does not exist")

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Tasks validation failed: {errors}")
    else:
        logger.info("Tasks validation passed")

    return is_valid, errors


def validate_tasks_json(content: str) -> Tuple[bool, List[str], Optional[List[Dict]]]:
    """Validate tasks.json content.

    Args:
        content: JSON string content

    Returns:
        Tuple of (is_valid, list_of_errors, parsed_tasks)
    """
    errors = []

    try:
        tasks = json.loads(content)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return False, errors, None

    if not isinstance(tasks, list):
        errors.append("tasks.json must contain a list")
        return False, errors, None

    is_valid, validation_errors = validate_tasks(tasks)
    errors.extend(validation_errors)

    return is_valid, errors, tasks if is_valid else None


def validate_coding_output(output: str) -> Tuple[bool, str]:
    """Validate coder agent output.

    Checks that output indicates successful completion.

    Args:
        output: Output from coder agent

    Returns:
        Tuple of (is_success, message)
    """
    output_lower = output.lower()

    # Check for explicit failure indicators
    failure_patterns = [
        "failed to", "error:", "cannot", "unable to",
        "exception", "traceback"
    ]

    for pattern in failure_patterns:
        if pattern in output_lower:
            return False, f"Failure pattern detected: '{pattern}'"

    # Check for success indicators
    success_patterns = [
        "completed", "implemented", "created", "written"
    ]

    has_success = any(pattern in output_lower for pattern in success_patterns)

    if has_success:
        return True, "Task completed successfully"
    elif len(output) > 100:
        # Assume success if there's substantial output without failure indicators
        return True, "Task appears complete (no failure indicators)"
    else:
        return False, "Insufficient output to determine success"


def validate_requirement(requirement: str) -> Tuple[bool, List[str]]:
    """Validate user requirement input.

    Args:
        requirement: User requirement string

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check minimum length
    if len(requirement.strip()) < 10:
        errors.append("Requirement is too short (minimum 10 characters)")

    # Check for meaningful content
    words = requirement.strip().split()
    if len(words) < 3:
        errors.append("Requirement must contain at least 3 words")

    # Check for common placeholders
    placeholders = ["...", "etc", "something", "anything"]
    requirement_lower = requirement.lower()
    for placeholder in placeholders:
        if placeholder in requirement_lower:
            errors.append(f"Requirement contains placeholder: '{placeholder}'")

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Requirement validation failed: {errors}")

    return is_valid, errors


def validate_session_workspace(workspace: Path) -> Tuple[bool, List[str]]:
    """Validate session workspace structure.

    Args:
        workspace: Path to session workspace

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not workspace.exists():
        errors.append(f"Workspace directory does not exist: {workspace}")
        return False, errors

    # Check for expected subdirectories
    expected_dirs = ["code", "artifacts"]
    for dir_name in expected_dirs:
        dir_path = workspace / dir_name
        if not dir_path.exists():
            errors.append(f"Missing expected directory: {dir_name}")

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Workspace validation failed: {errors}")

    return is_valid, errors


def extract_code_from_response(response: str) -> List[str]:
    """Extract code blocks from a response.

    Args:
        response: Agent response text

    Returns:
        List of code block contents
    """
    pattern = r"```(?:\w*)\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    return matches


def validate_json_output(content: str) -> Tuple[bool, Optional[Dict]]:
    """Validate and parse JSON output.

    Args:
        content: JSON string content

    Returns:
        Tuple of (is_valid, parsed_dict)
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return True, data
        return False, None
    except json.JSONDecodeError:
        return False, None


def sanitize_agent_output(output: str) -> str:
    """Sanitize agent output by removing problematic content.

    Args:
        output: Raw agent output

    Returns:
        Sanitized output
    """
    # Remove null bytes
    output = output.replace("\x00", "")

    # Remove excessive whitespace
    output = re.sub(r"\n{3,}", "\n\n", output)

    # Trim leading/trailing whitespace
    output = output.strip()

    return output


class OutputValidator:
    """Main validator for agent outputs."""

    @staticmethod
    def validate_prd_output(content: str) -> None:
        """Validate PRD and raise exception if invalid.

        Args:
            content: PRD content

        Raises:
            ValidationError: If validation fails
        """
        is_valid, errors = validate_prd(content)
        if not is_valid:
            raise ValidationError("PRD validation failed", errors)

    @staticmethod
    def validate_design_output(content: str) -> None:
        """Validate design and raise exception if invalid.

        Args:
            content: Design content

        Raises:
            ValidationError: If validation fails
        """
        is_valid, errors = validate_design(content)
        if not is_valid:
            raise ValidationError("Design validation failed", errors)

    @staticmethod
    def validate_tasks_output(tasks: List[Dict[str, Any]]) -> None:
        """Validate tasks and raise exception if invalid.

        Args:
            tasks: Task list

        Raises:
            ValidationError: If validation fails
        """
        is_valid, errors = validate_tasks(tasks)
        if not is_valid:
            raise ValidationError("Tasks validation failed", errors)

    @staticmethod
    def validate_coding_output(output: str) -> None:
        """Validate coding output and raise exception if failed.

        Args:
            output: Coder agent output

        Raises:
            ValidationError: If validation fails
        """
        is_success, message = validate_coding_output(output)
        if not is_success:
            raise ValidationError(f"Coding validation failed: {message}")
